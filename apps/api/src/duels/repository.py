"""Доступ к данным дуэльного домена: duels, ratings (FOR UPDATE), answers.

Все блокировки строк ratings берутся в детерминированном порядке user_id ASC
— защита от дедлоков при параллельных finish (ТЗ §4 п.5, duels.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import DuelStatus
from src.duels.models import Answer, Duel
from src.users.models import Rating


class DuelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_running(
        self,
        *,
        topic_id: uuid.UUID,
        player_a: uuid.UUID,
        player_b: uuid.UUID,
        started_at: datetime,
    ) -> Duel:
        duel = Duel(
            topic_id=topic_id,
            status=DuelStatus.running,
            player_a=player_a,
            player_b=player_b,
            started_at=started_at,
        )
        self._session.add(duel)
        await self._session.flush()
        return duel

    async def get(self, duel_id: uuid.UUID) -> Duel | None:
        return await self._session.get(Duel, duel_id)

    async def get_for_update(self, duel_id: uuid.UUID) -> Duel | None:
        """Берёт строку duels под блокировку (первый finish побеждает гонку)."""
        stmt = select(Duel).where(Duel.id == duel_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def ensure_rating_rows(
        self, *, user_ids: Sequence[uuid.UUID], topic_id: uuid.UUID
    ) -> None:
        """Создаёт недостающие строки ratings (дефолты из БД). Идемпотентно."""
        stmt = (
            pg_insert(Rating)
            .values([{"user_id": uid, "topic_id": topic_id} for uid in user_ids])
            .on_conflict_do_nothing(index_elements=["user_id", "topic_id"])
        )
        await self._session.execute(stmt)

    async def lock_ratings(
        self, *, user_ids: Sequence[uuid.UUID], topic_id: uuid.UUID
    ) -> dict[uuid.UUID, Rating]:
        """SELECT ... FOR UPDATE строк ratings в порядке user_id ASC."""
        stmt = (
            select(Rating)
            .where(Rating.user_id.in_(list(user_ids)), Rating.topic_id == topic_id)
            .order_by(Rating.user_id.asc())
            .with_for_update()
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.user_id: row for row in rows}

    async def insert_duel_answers(self, rows: list[dict[str, object]]) -> None:
        if rows:
            await self._session.execute(insert(Answer), rows)
