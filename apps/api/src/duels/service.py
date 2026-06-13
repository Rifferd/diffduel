"""Бизнес-логика дуэлей: создание дуэли и финальная транзакция (Эло).

Решения сверх спеки (задокументированы):
- Строки ratings обоих игроков создаются ЗАРАНЕЕ при создании дуэли
  (ensure_rating_rows). В finish дополнительно вызываем ensure_rating_rows
  идемпотентно — на случай дуэли, созданной иным путём, — затем берём
  обе строки SELECT ... FOR UPDATE в порядке user_id ASC.
- Идемпотентность finish: первым делом берём строку duels FOR UPDATE;
  если статус уже finished/aborted — возвращаем сохранённый результат,
  реконструируя deltas из колонок duels и elo из текущих строк ratings
  БЕЗ повторного начисления.
- duels.finished продюсируется в Kafka ТОЛЬКО после commit (best-effort).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import events
from src.core.enums import DuelStatus
from src.core.errors import NotFoundError, ValidationError
from src.core.logging import get_logger
from src.core.redis import get_redis
from src.duels import elo
from src.duels.models import Duel
from src.duels.repository import DuelRepository
from src.duels.schemas import (
    CreateDuelRequest,
    CreateDuelResponse,
    DuelCardResponse,
    DuelTask,
    FinishDuelRequest,
    FinishDuelResponse,
    PlayerResults,
)
from src.leaderboard.service import update_on_finish
from src.tasks.repository import TaskRepository
from src.topics.models import Task
from src.users.models import Rating

logger = get_logger("duels")

_DUELS_FINISHED_TOPIC = "duels.finished"
_TASKS_PER_DUEL = 5


@dataclass(slots=True)
class _Settled:
    response: FinishDuelResponse
    scores: dict[str, int]


class DuelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._duels = DuelRepository(session)
        self._tasks = TaskRepository(session)

    # --- create --------------------------------------------------------------

    async def create(self, data: CreateDuelRequest) -> CreateDuelResponse:
        topic_id = await self._tasks.topic_id_by_slug(data.topic)
        if topic_id is None:
            raise NotFoundError("Тема не найдена", code="topic_not_found")

        tasks: Sequence[Task] = await self._tasks.random_published(
            topic_id=topic_id, difficulty=None, limit=_TASKS_PER_DUEL
        )
        if len(tasks) < _TASKS_PER_DUEL:
            raise ValidationError(
                "Недостаточно опубликованных задач темы для дуэли",
                code="not_enough_tasks",
            )

        duel = await self._duels.create_running(
            topic_id=topic_id,
            player_a=data.player_a,
            player_b=data.player_b,
            started_at=datetime.now(tz=UTC),
        )
        # Заводим строки рейтингов обоих игроков заранее — finish их только лочит.
        await self._duels.ensure_rating_rows(
            user_ids=[data.player_a, data.player_b], topic_id=topic_id
        )
        ratings = await self._duels.lock_ratings(
            user_ids=[data.player_a, data.player_b], topic_id=topic_id
        )
        await self._session.commit()

        return CreateDuelResponse(
            duel_id=duel.id,
            topic=data.topic,
            tasks=[DuelTask.model_validate(task) for task in tasks],
            ratings={
                str(data.player_a): ratings[data.player_a].elo,
                str(data.player_b): ratings[data.player_b].elo,
            },
        )

    # --- share-карточка (image-gen воркер) -----------------------------------

    async def get_card(self, duel_id: uuid.UUID) -> DuelCardResponse:
        """Данные для рендера share-карточки + текущий ключ (идемпотентность)."""
        duel = await self._duels.get(duel_id)
        if duel is None:
            raise NotFoundError("Дуэль не найдена", code="duel_not_found")
        usernames = await self._duels.usernames_of([duel.player_a, duel.player_b])
        return DuelCardResponse(
            duel_id=duel.id,
            winner_id=duel.winner_id,
            usernames={str(uid): name for uid, name in usernames.items()},
            deltas=_deltas_payload(duel),
            share_card_key=duel.share_card_key,
        )

    async def set_share_card(self, duel_id: uuid.UUID, key: str) -> None:
        """Записывает ключ карточки идемпотентно (повторное событие — no-op)."""
        if await self._duels.get(duel_id) is None:
            raise NotFoundError("Дуэль не найдена", code="duel_not_found")
        await self._duels.set_share_card_key(duel_id, key)

    # --- finish --------------------------------------------------------------

    async def finish(self, duel_id: uuid.UUID, data: FinishDuelRequest) -> FinishDuelResponse:
        # 1) Блокируем строку duels первым шагом — арбитр гонки конкурентных finish.
        duel = await self._duels.get_for_update(duel_id)
        if duel is None:
            raise NotFoundError("Дуэль не найдена", code="duel_not_found")

        # 2) Идемпотентность: уже завершена — отдаём сохранённый результат.
        if duel.status in (DuelStatus.finished, DuelStatus.aborted):
            return await self._stored_result(duel)

        # Контракт finish ожидает ровно двух игроков — A и B этой дуэли.
        if set(data.results) != {str(duel.player_a), str(duel.player_b)}:
            raise ValidationError(
                "results должен содержать ровно обоих игроков дуэли",
                code="invalid_results",
            )

        # 3) reason=aborted — статус aborted, Эло не трогаем, ответы не пишем.
        if data.reason == "aborted":
            duel.status = DuelStatus.aborted
            duel.finished_at = data.finished_at
            duel.winner_id = None
            duel.rating_delta_a = None
            duel.rating_delta_b = None
            await self._session.commit()
            await self._emit_finished(duel, scores={})
            return FinishDuelResponse(winner_id=None, deltas={}, elo={})

        settled = await self._settle(duel, data)
        await self._session.commit()
        await self._emit_finished(duel, scores=settled.scores)
        # ZSET-лидерборды обновляем ПОСЛЕ commit, вне транзакции БД (спека A).
        await self._update_leaderboards(duel, settled.response.elo)
        return settled.response

    # --- внутреннее ----------------------------------------------------------

    async def _settle(self, duel: Duel, data: FinishDuelRequest) -> _Settled:
        a, b = duel.player_a, duel.player_b
        res_a = data.results[str(a)]
        res_b = data.results[str(b)]

        score_a, time_a = _score(res_a)
        score_b, time_b = _score(res_b)
        outcome_a = _outcome_a(score_a, time_a, score_b, time_b)

        # Строки рейтингов под блокировкой (порядок user_id ASC внутри репозитория).
        await self._duels.ensure_rating_rows(user_ids=[a, b], topic_id=duel.topic_id)
        ratings = await self._duels.lock_ratings(user_ids=[a, b], topic_id=duel.topic_id)
        rating_a, rating_b = ratings[a], ratings[b]

        elo_out = elo.compute(rating_a.elo, rating_b.elo, outcome_a)

        _apply_stats(rating_a, delta=elo_out.delta_a, won=outcome_a == 1.0)
        _apply_stats(rating_b, delta=elo_out.delta_b, won=outcome_a == 0.0)

        winner_id: uuid.UUID | None
        if outcome_a == 1.0:
            winner_id = a
        elif outcome_a == 0.0:
            winner_id = b
        else:
            winner_id = None

        duel.status = DuelStatus.finished
        duel.finished_at = data.finished_at
        duel.winner_id = winner_id
        duel.rating_delta_a = elo_out.delta_a
        duel.rating_delta_b = elo_out.delta_b

        # answers с duel_id: selected=null → is_correct=false; time_ms NULL → 0 (NOT NULL).
        rows: list[dict[str, object]] = []
        for user_id, res in ((a, res_a), (b, res_b)):
            for ans in res.answers:
                rows.append(
                    {
                        "duel_id": duel.id,
                        "user_id": user_id,
                        "task_id": ans.task_id,
                        "is_correct": bool(ans.correct) and ans.selected is not None,
                        "time_ms": ans.time_ms if ans.time_ms is not None else 0,
                        "submitted_at": data.finished_at,
                    }
                )
        await self._duels.insert_duel_answers(rows)

        response = FinishDuelResponse(
            winner_id=winner_id,
            deltas={str(a): elo_out.delta_a, str(b): elo_out.delta_b},
            elo={str(a): elo_out.new_elo_a, str(b): elo_out.new_elo_b},
        )
        return _Settled(response=response, scores={str(a): score_a, str(b): score_b})

    async def _stored_result(self, duel: Duel) -> FinishDuelResponse:
        """Реконструирует сохранённый результат без повторного начисления."""
        if duel.status == DuelStatus.aborted or duel.rating_delta_a is None:
            return FinishDuelResponse(winner_id=duel.winner_id, deltas={}, elo={})
        a, b = duel.player_a, duel.player_b
        delta_b = duel.rating_delta_b if duel.rating_delta_b is not None else 0
        current = await self._current_elo(duel)
        return FinishDuelResponse(
            winner_id=duel.winner_id,
            deltas={str(a): duel.rating_delta_a, str(b): delta_b},
            elo=current,
        )

    async def _current_elo(self, duel: Duel) -> dict[str, int]:
        """Текущие elo обоих игроков (для идемпотентного повтора), без блокировки."""
        stmt = select(Rating).where(
            Rating.user_id.in_([duel.player_a, duel.player_b]),
            Rating.topic_id == duel.topic_id,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        by_user = {row.user_id: row.elo for row in rows}
        return {
            str(duel.player_a): by_user.get(duel.player_a, elo.BASE_RATING),
            str(duel.player_b): by_user.get(duel.player_b, elo.BASE_RATING),
        }

    async def _emit_finished(self, duel: Duel, *, scores: dict[str, int]) -> None:
        payload: dict[str, object] = {
            "duel_id": str(duel.id),
            "topic": str(duel.topic_id),
            "players": [str(duel.player_a), str(duel.player_b)],
            "winner_id": str(duel.winner_id) if duel.winner_id else None,
            "deltas": _deltas_payload(duel),
            "scores": scores,
        }
        await events.produce(
            _DUELS_FINISHED_TOPIC,
            key=str(duel.id),
            event_type="duels.finished",
            payload=payload,
        )

    async def _update_leaderboards(self, duel: Duel, new_elo: dict[str, int]) -> None:
        """ZADD обоих игроков в lb:topic/lb:weekly/lb:global. Best-effort.

        Падение Redis не должно ронять уже зафиксированный finish — логируем.
        """
        try:
            slug = await self._duels.topic_slug(duel.topic_id)
            if slug is None:
                return
            await update_on_finish(
                get_redis(),
                topic_slug=slug,
                new_elo={uuid.UUID(uid): val for uid, val in new_elo.items()},
            )
        except Exception:
            logger.warning("leaderboard_update_failed", duel_id=str(duel.id))


def _outcome_a(score_a: int, time_a: int, score_b: int, time_b: int) -> float:
    """Исход для A: счёт → тай-брейк (меньшее суммарное время верных) → ничья."""
    if score_a != score_b:
        return 1.0 if score_a > score_b else 0.0
    if time_a != time_b:
        return 1.0 if time_a < time_b else 0.0
    return 0.5


def _deltas_payload(duel: Duel) -> dict[str, int]:
    if duel.rating_delta_a is None:
        return {}
    return {
        str(duel.player_a): duel.rating_delta_a,
        str(duel.player_b): duel.rating_delta_b if duel.rating_delta_b is not None else 0,
    }


def _score(results: PlayerResults) -> tuple[int, int]:
    """Возвращает (число верных, суммарное время по верным ответам, мс)."""
    correct = 0
    time_sum = 0
    for ans in results.answers:
        if ans.correct and ans.selected is not None:
            correct += 1
            if ans.time_ms is not None:
                time_sum += ans.time_ms
    return correct, time_sum


def _apply_stats(rating: Rating, *, delta: int, won: bool) -> None:
    rating.elo += delta
    rating.games += 1
    if won:
        rating.wins += 1
        rating.streak += 1
    else:
        rating.streak = 0
