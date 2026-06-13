"""Бизнес-логика дневного челленджа.

- GET /daily: ленивый атомарный выбор задачи дня (ON CONFLICT), без эталона.
- POST /daily/answer: проверка checker'ом; ОДИН зачётный ответ в день (ZADD NX);
  повторные считаются и возвращают результат, но в лидерборд не идут.
- Лидерборд: ZSET lb:daily:{date}, score = (верно: BONUS − время_мс; неверно: 0).
  Обогащение никами батчем (LeaderboardPgRepository, без N+1).

Решение сверх спеки: задача дня — published любой темы (спека не ограничивает
тему). Скоринг неверного ответа кладёт 0 в ZSET, чтобы зафиксировать «сыграл
сегодня» и не дать второй зачётной попытки (членство = участие).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.avatars import avatar_url
from src.core.errors import NotFoundError
from src.core.telemetry import measure_answer_check
from src.daily.repository import DailyPgRepository, DailyRedisRepository
from src.daily.schemas import (
    DailyAnswerResult,
    DailyAnswerSubmit,
    DailyLeaderboardEntry,
    DailyMyPosition,
    DailyTask,
)
from src.leaderboard.repository import LeaderboardPgRepository
from src.tasks.checker import check_answer
from src.tasks.repository import TaskRepository
from src.tasks.schemas import TaskPublic

# Верный ответ: большой бонус минус затраченное время (быстрее → выше score).
# 600_000 мс = верхняя граница time_ms (AnswerSubmit), бонус строго больше неё,
# поэтому любой верный ответ всегда > 0 (неверного, у которого score=0).
_CORRECT_BONUS = 1_000_000


def _utc_today() -> date:
    return datetime.now(tz=UTC).date()


class DailyService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._pg = DailyPgRepository(session)
        self._zset = DailyRedisRepository(redis)
        self._tasks = TaskRepository(session)

    async def task_of_day(self) -> DailyTask:
        """Возвращает задачу дня, лениво фиксируя её при первом обращении."""
        day = _utc_today()
        task_id = await self._pg.get_challenge_task_id(day)
        if task_id is None:
            candidate = await self._pg.random_published_task_id()
            if candidate is None:
                raise NotFoundError("Нет опубликованных задач", code="no_published_tasks")
            task_id = await self._pg.fix_challenge(day, candidate)

        task = await self._pg.get_task(task_id)
        if task is None:
            # Зафиксированная задача снята с публикации — пограничный случай.
            raise NotFoundError("Задача дня недоступна", code="daily_task_unavailable")
        return DailyTask(challenge_date=day, task=TaskPublic.model_validate(task))

    async def submit(self, *, user_id: uuid.UUID, data: DailyAnswerSubmit) -> DailyAnswerResult:
        day = _utc_today()
        task_id = await self._pg.get_challenge_task_id(day)
        if task_id is None:
            raise NotFoundError("Задача дня ещё не выбрана", code="daily_not_started")
        task = await self._pg.get_task(task_id)
        if task is None:
            raise NotFoundError("Задача дня недоступна", code="daily_task_unavailable")

        with measure_answer_check(mode="daily") as m:
            result = check_answer(task.type, task.answer, data.answer.model_dump())
            m.correct = result.correct

        # Зачёт только первого ответа за день (членство в ZSET = «уже сыграл»).
        already = await self._zset.already_scored(day, user_id)

        await self._tasks.record_answer(
            user_id=user_id,
            task_id=task.id,
            is_correct=result.correct,
            time_ms=data.time_ms,
            submitted_at=datetime.now(tz=UTC),
        )
        await self._session.commit()

        scored = False
        if not already:
            score = _CORRECT_BONUS - data.time_ms if result.correct else 0
            # ZADD NX: защищает от гонки параллельных первых ответов.
            scored = await self._zset.add_first_score(day, user_id, score)

        return DailyAnswerResult(
            correct=result.correct,
            correct_option=result.correct_option,
            explanation=task.explanation or "",
            scored=scored,
            already_answered=already,
        )

    async def leaderboard(self, *, limit: int) -> list[DailyLeaderboardEntry]:
        day = _utc_today()
        ranked = await self._zset.top(day, limit)
        cards = await LeaderboardPgRepository(self._session).user_cards([uid for uid, _ in ranked])
        out: list[DailyLeaderboardEntry] = []
        rank = 0
        for uid, score in ranked:
            card = cards.get(uid)
            if card is None:
                continue  # забанен/удалён — не светим
            rank += 1
            out.append(
                DailyLeaderboardEntry(
                    rank=rank,
                    user_id=uid,
                    username=card.username,
                    avatar_url=avatar_url(card.avatar_key),
                    score=score,
                )
            )
        return out

    async def my_position(self, *, user_id: uuid.UUID) -> DailyMyPosition:
        day = _utc_today()
        rank, score = await self._zset.rank_and_score(day, user_id)
        return DailyMyPosition(rank=rank, score=score)
