"""Доступ к данным daily: фиксация задачи дня (PG), дневной ZSET (Redis).

- Задача дня лениво фиксируется атомарно (INSERT ... ON CONFLICT DO NOTHING).
- Дневной лидерборд — Redis ZSET ``lb:daily:{date}``; членство = «уже сыграл
  сегодня» (зачёт только первого ответа через ZADD NX). Обогащение никами —
  батчем из PG (переиспользуем LeaderboardPgRepository, без N+1).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import TaskStatus
from src.daily.keys import daily_key
from src.daily.models import DailyChallenge
from src.topics.models import Task


class DailyPgRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_challenge_task_id(self, day: date) -> uuid.UUID | None:
        stmt = select(DailyChallenge.task_id).where(DailyChallenge.challenge_date == day)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def random_published_task_id(self) -> uuid.UUID | None:
        """Случайная published-задача (любой темы) — кандидат в задачу дня."""
        stmt = (
            select(Task.id)
            .where(Task.status == TaskStatus.published)
            .order_by(func.random())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def fix_challenge(self, day: date, task_id: uuid.UUID) -> uuid.UUID:
        """Атомарно фиксирует задачу дня. ON CONFLICT — возвращает уже зафиксированную.

        Гонка: два параллельных GET /daily выберут разные random-задачи, но
        вставить сможет только один; второй получит DO NOTHING и перечитает строку.
        """
        stmt = (
            pg_insert(DailyChallenge)
            .values(challenge_date=day, task_id=task_id)
            .on_conflict_do_nothing(index_elements=["challenge_date"])
        )
        await self._session.execute(stmt)
        await self._session.commit()
        # Перечитываем источник истины (мог зафиксировать конкурент).
        existing = await self.get_challenge_task_id(day)
        return existing if existing is not None else task_id

    async def get_task(self, task_id: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.id == task_id, Task.status == TaskStatus.published)
        return (await self._session.execute(stmt)).scalar_one_or_none()


class DailyRedisRepository:
    """Дневной ZSET-лидерборд. member=str(user_id), score=int."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def already_scored(self, day: date, user_id: uuid.UUID) -> bool:
        """Есть ли уже зачётный ответ пользователя за день (членство в ZSET)."""
        score = await self._redis.zscore(daily_key(day), str(user_id))
        return score is not None

    async def add_first_score(self, day: date, user_id: uuid.UUID, score: int) -> bool:
        """ZADD NX — записывает score только если игрока ещё нет. True, если записали."""
        added = await self._redis.zadd(daily_key(day), {str(user_id): float(score)}, nx=True)
        return added is not None and int(added) == 1

    async def top(self, day: date, limit: int) -> list[tuple[uuid.UUID, int]]:
        rows = cast(
            "list[tuple[str, float]]",
            await self._redis.zrevrange(daily_key(day), 0, limit - 1, withscores=True),
        )
        return [(uuid.UUID(member), int(score)) for member, score in rows]

    async def rank_and_score(self, day: date, user_id: uuid.UUID) -> tuple[int | None, int | None]:
        key = daily_key(day)
        rank = cast("int | None", await self._redis.zrevrank(key, str(user_id)))
        if rank is None:
            return None, None
        score = await self._redis.zscore(key, str(user_id))
        return int(rank) + 1, int(score) if score is not None else None
