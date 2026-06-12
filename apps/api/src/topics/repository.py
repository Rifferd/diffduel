"""Доступ к данным домена topics."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.topics.models import Topic


class TopicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> Sequence[Topic]:
        stmt = select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.title)
        return (await self._session.execute(stmt)).scalars().all()
