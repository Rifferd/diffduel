"""Бизнес-логика турниров.

- Список/детали: число участников и лидерборд без N+1 (JOIN в репозитории).
- Вход (enter): платёж — ЗАГЛУШКА (ManualProvider). entry_fee=0 → пускаем
  бесплатно; entry_fee>0 → 402 ``entry_payment_unavailable`` (вход выдаёт админ
  через grant-entry). Повторный вход — 200 (идемпотентно).
- Задачи: только участнику активного турнира, без эталонов (TaskPublic).
- Ответ: проверка checker'ом; ОДИН зачётный ответ на задачу (tournament_answers
  ON CONFLICT); score/time накапливаются в entry. По ответу на все задачи
  турнира фиксируется finished_at.
- Места: RANK() OVER (ORDER BY score DESC, time_ms ASC) — при завершении турнира
  (admin set_status=finished) или по запросу recompute.

Скоринг (решение сверх спеки, как в daily): верный ответ = BONUS − time_ms
(быстрее → выше), неверный = 0. BONUS > верхней границы time_ms, поэтому любой
верный ответ всегда даёт положительный вклад.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.providers.manual import ManualProvider
from src.core.avatars import avatar_url
from src.core.enums import TournamentStatus
from src.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PaymentRequiredError,
)
from src.core.telemetry import measure_answer_check
from src.tasks.checker import check_answer
from src.tasks.schemas import TaskPublic
from src.tournaments.models import Tournament, TournamentEntry
from src.tournaments.repository import TournamentRepository
from src.tournaments.schemas import (
    EnterResult,
    TournamentAnswerResult,
    TournamentAnswerSubmit,
    TournamentDetail,
    TournamentLeaderboardEntry,
    TournamentSummary,
    TournamentTasks,
)

# Верный ответ: бонус минус время (зеркалит daily). 600_000 = верхняя граница
# time_ms, бонус строго больше — верный вклад всегда > 0.
_CORRECT_BONUS = 1_000_000


class TournamentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TournamentRepository(session)
        # Тот же провайдер-заглушка, что и для Pro (release2): онлайн-оплаты нет.
        self._payment = ManualProvider()
        self._payment_unavailable_message = (
            "Онлайн-оплата входа недоступна, обратитесь к администратору."
        )

    async def list_tournaments(self, *, status: TournamentStatus | None) -> list[TournamentSummary]:
        rows = await self._repo.list_tournaments(status=status)
        return [
            TournamentSummary(
                id=t.id,
                title=t.title,
                topic_id=t.topic_id,
                starts_at=t.starts_at,
                ends_at=t.ends_at,
                entry_fee=t.entry_fee,
                prize_pool=t.prize_pool,
                status=t.status,
                entries_count=cnt,
            )
            for t, cnt in rows
        ]

    async def detail(self, tournament_id: uuid.UUID) -> TournamentDetail:
        tournament = await self._require_tournament(tournament_id)
        leaderboard = await self._repo.leaderboard(tournament_id)
        return TournamentDetail(
            id=tournament.id,
            title=tournament.title,
            topic_id=tournament.topic_id,
            starts_at=tournament.starts_at,
            ends_at=tournament.ends_at,
            entry_fee=tournament.entry_fee,
            prize_pool=tournament.prize_pool,
            status=tournament.status,
            tasks_count=len(tournament.task_ids),
            entries_count=len(leaderboard),
            leaderboard=[
                TournamentLeaderboardEntry(
                    user_id=row.user_id,
                    username=row.username,
                    avatar_url=avatar_url(row.avatar_key),
                    score=row.score,
                    time_ms=row.time_ms,
                    place=row.place,
                )
                for row in leaderboard
            ],
        )

    async def enter(self, *, tournament_id: uuid.UUID, user_id: uuid.UUID) -> EnterResult:
        tournament = await self._require_tournament(tournament_id)
        if tournament.status == TournamentStatus.finished:
            raise ConflictError("Турнир завершён", code="tournament_finished")

        if await self._repo.get_entry(tournament_id, user_id) is not None:
            return EnterResult(joined=False, already_entered=True)

        # Платёж — ЗАГЛУШКА: платный вход недоступен онлайн, выдаёт админ.
        # Сообщение берём у ManualProvider (тот же провайдер, что и Pro-оплата).
        if tournament.entry_fee > Decimal("0"):
            raise PaymentRequiredError(
                self._payment_unavailable_message, code="entry_payment_unavailable"
            )

        joined = await self._repo.create_entry_if_absent(tournament_id, user_id)
        await self._session.commit()
        return EnterResult(joined=joined, already_entered=not joined)

    async def grant_entry(self, *, tournament_id: uuid.UUID, user_id: uuid.UUID) -> EnterResult:
        """Ручная выдача входа (заглушка оплаты) — вызывается из админки."""
        await self._require_tournament(tournament_id)
        joined = await self._repo.create_entry_if_absent(tournament_id, user_id)
        await self._session.commit()
        return EnterResult(joined=joined, already_entered=not joined)

    async def tasks(self, *, tournament_id: uuid.UUID, user_id: uuid.UUID) -> TournamentTasks:
        tournament = await self._require_tournament(tournament_id)
        await self._require_active(tournament.status)
        await self._require_participant(tournament_id, user_id)

        loaded = await self._repo.tasks_public(tournament.task_ids)
        # Порядок — как в task_ids; снятые с публикации пропускаем.
        tasks = [
            TaskPublic.model_validate(loaded[tid]) for tid in tournament.task_ids if tid in loaded
        ]
        return TournamentTasks(tasks=tasks)

    async def submit(
        self,
        *,
        tournament_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TournamentAnswerSubmit,
    ) -> TournamentAnswerResult:
        tournament = await self._require_tournament(tournament_id)
        await self._require_active(tournament.status)
        await self._require_participant(tournament_id, user_id)

        if data.task_id not in tournament.task_ids:
            raise NotFoundError("Задача не входит в турнир", code="task_not_in_tournament")
        task = await self._repo.get_task(data.task_id)
        if task is None:
            raise NotFoundError("Задача недоступна", code="task_unavailable")

        with measure_answer_check(mode="tournament") as m:
            result = check_answer(task.type, task.answer, data.answer.model_dump())
            m.correct = result.correct

        # Один зачётный ответ на задачу: вставка-маркер с ON CONFLICT DO NOTHING.
        scored = await self._repo.record_scored_answer(
            tournament_id=tournament_id, user_id=user_id, task_id=data.task_id
        )

        gained = 0
        finished = False
        if scored:
            gained = _CORRECT_BONUS - data.time_ms if result.correct else 0
            answered = await self._repo.answered_task_ids(tournament_id, user_id)
            all_done = set(tournament.task_ids).issubset(answered)
            finished_at = datetime.now(tz=UTC) if all_done else None
            entry = await self._repo.add_entry_score(
                tournament_id=tournament_id,
                user_id=user_id,
                add_score=gained,
                add_time_ms=data.time_ms,
                finished_at=finished_at,
            )
            finished = entry.finished_at is not None
            current_score = int(entry.score or 0)
        else:
            entry = await self._require_entry(tournament_id, user_id)
            finished = entry.finished_at is not None
            current_score = int(entry.score or 0)

        await self._session.commit()
        return TournamentAnswerResult(
            correct=result.correct,
            correct_option=result.correct_option,
            explanation=task.explanation or "",
            scored=scored,
            already_answered=not scored,
            score=current_score,
            finished=finished,
        )

    async def recompute_places(self, tournament_id: uuid.UUID) -> None:
        await self._require_tournament(tournament_id)
        await self._repo.recompute_places(tournament_id)
        await self._session.commit()

    # --- helpers -------------------------------------------------------------

    async def _require_tournament(self, tournament_id: uuid.UUID) -> Tournament:
        tournament = await self._repo.get(tournament_id)
        if tournament is None:
            raise NotFoundError("Турнир не найден", code="tournament_not_found")
        return tournament

    async def _require_entry(self, tournament_id: uuid.UUID, user_id: uuid.UUID) -> TournamentEntry:
        entry = await self._repo.get_entry(tournament_id, user_id)
        if entry is None:
            raise ForbiddenError("Вы не участник турнира", code="not_participant")
        return entry

    async def _require_participant(self, tournament_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if await self._repo.get_entry(tournament_id, user_id) is None:
            raise ForbiddenError("Вы не участник турнира", code="not_participant")

    async def _require_active(self, status: TournamentStatus) -> None:
        if status != TournamentStatus.active:
            raise ConflictError("Турнир не активен", code="tournament_not_active")
