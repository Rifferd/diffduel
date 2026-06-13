"""Доступ к данным домена users."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import DuelStatus
from src.topics.models import Topic
from src.users.models import Rating, User


@dataclass(slots=True, frozen=True)
class TopicElo:
    slug: str
    title: str
    elo: int


@dataclass(slots=True, frozen=True)
class ProfileStats:
    total_duels: int
    wins: int
    streak: int


class UserRepository:
    """Репозиторий пользователей. Никакой бизнес-логики — только доступ к данным."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def exists_email(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email)
        return (await self._session.execute(stmt)).first() is not None

    async def exists_username(self, username: str) -> bool:
        stmt = select(User.id).where(User.username == username)
        return (await self._session.execute(stmt)).first() is not None

    async def create(self, *, email: str, username: str, password_hash: str) -> User:
        user = User(email=email, username=username, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_username(self, user: User, username: str) -> User:
        user.username = username
        await self._session.flush()
        return user

    async def update_avatar_key(self, user: User, avatar_key: str) -> User:
        user.avatar_key = avatar_key
        await self._session.flush()
        return user

    # --- Публичный профиль (витрина статистики) ------------------------------

    async def topic_ratings(self, user_id: uuid.UUID) -> list[TopicElo]:
        """Эло пользователя по темам (JOIN ratings+topics), активные темы."""
        stmt = (
            select(Rating.elo, Topic.slug, Topic.title)
            .join(Topic, Topic.id == Rating.topic_id)
            .where(Rating.user_id == user_id, Topic.is_active.is_(True))
            .order_by(Rating.elo.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [TopicElo(slug=r.slug, title=r.title, elo=r.elo) for r in rows]

    async def profile_stats(self, user_id: uuid.UUID) -> ProfileStats:
        """Агрегаты по завершённым дуэлям игрока одним запросом.

        total/wins — count-агрегаты; streak — число подряд идущих побед с конца
        (по finished_at desc) через оконную сумму поражений как "сброс серии".
        Raw SQL — допустимая витрина статистики (conventions §SQL), параметры
        связаны через bindparam (без конкатенации).
        """
        stmt = text(
            """
            WITH my_duels AS (
                SELECT
                    d.finished_at,
                    (d.winner_id = :uid) AS is_win
                FROM duels d
                WHERE d.status = CAST(:finished AS duel_status)
                  AND (d.player_a = :uid OR d.player_b = :uid)
            ),
            ordered AS (
                SELECT
                    is_win,
                    SUM(CASE WHEN NOT is_win THEN 1 ELSE 0 END)
                        OVER (ORDER BY finished_at DESC
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS losses_so_far
                FROM my_duels
            )
            SELECT
                (SELECT count(*) FROM my_duels) AS total_duels,
                (SELECT count(*) FROM my_duels WHERE is_win) AS wins,
                (SELECT count(*) FROM ordered WHERE losses_so_far = 0 AND is_win) AS streak
            """
        ).bindparams(
            bindparam("uid", value=user_id),
            bindparam("finished", value=DuelStatus.finished.value),
        )
        row = (await self._session.execute(stmt)).one()
        return ProfileStats(
            total_duels=int(row.total_duels),
            wins=int(row.wins),
            streak=int(row.streak),
        )
