"""Доступ к данным лидербордов: Redis ZSET + батч-обогащение из PG.

Redis — производный кэш (O(log N) чтение); источник истины по Эло — таблица
ratings. Обогащение username/avatar строго батчем (WHERE id = ANY) — без N+1.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.topics.models import Topic
from src.users.models import Rating, User


@dataclass(slots=True, frozen=True)
class RankedMember:
    """Член ZSET с рангом и score (Эло)."""

    rank: int
    user_id: uuid.UUID
    elo: int


@dataclass(slots=True, frozen=True)
class UserCard:
    """Карточка пользователя для обогащения строки лидерборда."""

    user_id: uuid.UUID
    username: str
    avatar_key: str | None


class LeaderboardRedisRepository:
    """ZSET-операции лидербордов. Member=str(user_id), score=elo."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def card_count(self, key: str) -> int:
        return int(await self._redis.zcard(key))

    async def update_member(self, key: str, user_id: uuid.UUID, elo: int) -> None:
        """ZADD одного игрока (новый score = его Эло)."""
        await self._redis.zadd(key, {str(user_id): float(elo)})

    async def update_member_max(self, key: str, user_id: uuid.UUID, elo: int) -> None:
        """ZADD с GT — score только растёт (для lb:global = max Эло по темам)."""
        await self._redis.zadd(key, {str(user_id): float(elo)}, gt=True)

    async def top(self, key: str, limit: int) -> list[RankedMember]:
        """ZREVRANGE топ-N WITHSCORES → ранжированный список (rank с 1)."""
        return await self.range_with_scores(key, 0, limit - 1)

    async def rank_of(self, key: str, user_id: uuid.UUID) -> int | None:
        """0-based ZREVRANK или None, если игрока нет в ZSET."""
        rank = cast("int | None", await self._redis.zrevrank(key, str(user_id)))
        return int(rank) if rank is not None else None

    async def range_with_scores(self, key: str, start: int, stop: int) -> list[RankedMember]:
        """ZREVRANGE [start, stop] WITHSCORES (rank = абсолютная позиция с 1)."""
        if start < 0:
            start = 0
        # decode_responses=True → member: str, score: float; стабы шире, поэтому cast.
        rows = cast(
            "list[tuple[str, float]]",
            await self._redis.zrevrange(key, start, stop, withscores=True),
        )
        return [
            RankedMember(rank=start + i + 1, user_id=uuid.UUID(member), elo=int(score))
            for i, (member, score) in enumerate(rows)
        ]

    async def replace(self, key: str, members: dict[str, float]) -> None:
        """Атомарно (pipeline) заменяет содержимое ZSET — для регидратации."""
        pipe = self._redis.pipeline(transaction=True)
        pipe.delete(key)
        if members:
            pipe.zadd(key, members)
        await pipe.execute()


class LeaderboardPgRepository:
    """Чтение источника истины (PG): обогащение карточками и регидратация."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_cards(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, UserCard]:
        """Батч-загрузка карточек: один WHERE id = ANY(:ids). Забаненных пропускаем."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.username, User.avatar_key).where(
            User.id.in_(list(user_ids)),
            User.banned_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            row.id: UserCard(user_id=row.id, username=row.username, avatar_key=row.avatar_key)
            for row in rows
        }

    async def ratings_by_topic(self, slug: str) -> list[tuple[uuid.UUID, int]]:
        """Все (user_id, elo) активной темы — для регидратации lb:topic/lb:weekly."""
        stmt = (
            select(Rating.user_id, Rating.elo)
            .join(Topic, Topic.id == Rating.topic_id)
            .where(Topic.slug == slug)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row.user_id, row.elo) for row in rows]

    async def max_elo_per_user(self) -> list[tuple[uuid.UUID, int]]:
        """(user_id, max elo по темам) — для регидратации lb:global."""
        from sqlalchemy import func

        stmt = select(Rating.user_id, func.max(Rating.elo)).group_by(Rating.user_id)
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], int(row[1])) for row in rows]

    async def active_topic_slugs(self) -> list[str]:
        stmt = select(Topic.slug).where(Topic.is_active.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())
