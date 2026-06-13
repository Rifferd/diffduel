"""Доступ к данным админки: задачи, пользователи, метрики, фиче-флаги."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.models import FeatureFlag
from src.billing.models import Subscription
from src.core.enums import TaskStatus
from src.duels.models import Duel
from src.topics.models import Task
from src.users.models import User


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Tasks ---------------------------------------------------------------

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None,
        topic_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Task], int]:
        conds = []
        if status is not None:
            conds.append(Task.status == status)
        if topic_id is not None:
            conds.append(Task.topic_id == topic_id)

        base = select(Task)
        if conds:
            base = base.where(*conds)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        stmt = base.order_by(Task.id).limit(limit).offset(offset)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, int(total or 0)

    async def get_task(self, task_id: uuid.UUID) -> Task | None:
        return await self._session.get(Task, task_id)

    async def add_task(self, task: Task) -> Task:
        self._session.add(task)
        await self._session.flush()
        return task

    async def topic_exists(self, topic_id: uuid.UUID) -> bool:
        from src.topics.models import Topic

        stmt = select(Topic.id).where(Topic.id == topic_id)
        return (await self._session.execute(stmt)).first() is not None

    # --- Users ---------------------------------------------------------------

    async def list_users(
        self, *, q: str | None, limit: int, offset: int
    ) -> tuple[Sequence[User], int]:
        base = select(User)
        if q:
            pattern = f"%{q}%"
            base = base.where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        stmt = base.order_by(User.created_at.desc()).limit(limit).offset(offset)
        items = (await self._session.execute(stmt)).scalars().all()
        return items, int(total or 0)

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def set_banned_at(self, user: User, value: datetime | None) -> User:
        user.banned_at = value
        await self._session.flush()
        return user

    # --- Metrics -------------------------------------------------------------

    async def count_users(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(User)) or 0)

    async def count_duels_since(self, since: datetime) -> int:
        stmt = select(func.count()).select_from(Duel).where(Duel.finished_at >= since)
        return int(await self._session.scalar(stmt) or 0)

    async def count_published_tasks(self) -> int:
        stmt = select(func.count()).select_from(Task).where(Task.status == TaskStatus.published)
        return int(await self._session.scalar(stmt) or 0)

    async def count_active_subscriptions(self) -> int:
        stmt = select(func.count()).select_from(Subscription).where(Subscription.status == "active")
        return int(await self._session.scalar(stmt) or 0)

    # --- Feature flags -------------------------------------------------------

    async def list_flags(self) -> Sequence[FeatureFlag]:
        stmt = select(FeatureFlag).order_by(FeatureFlag.key)
        return (await self._session.execute(stmt)).scalars().all()

    async def upsert_flag(
        self, *, key: str, enabled: bool, payload: dict[str, object] | None, now: datetime
    ) -> FeatureFlag:
        stmt = (
            pg_insert(FeatureFlag)
            .values(key=key, enabled=enabled, payload=payload)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"enabled": enabled, "payload": payload, "updated_at": now},
            )
            .returning(FeatureFlag)
        )
        flag = (await self._session.execute(stmt)).scalar_one()
        return flag
