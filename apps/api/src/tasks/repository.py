"""Доступ к данным домена tasks: выборка тренировочных задач, запись ответов."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import TaskStatus
from src.duels.models import Answer
from src.topics.models import Task, Topic


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def topic_id_by_slug(self, slug: str) -> uuid.UUID | None:
        stmt = select(Topic.id).where(Topic.slug == slug, Topic.is_active.is_(True))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def random_published(
        self,
        *,
        topic_id: uuid.UUID,
        difficulty: int | None,
        limit: int,
    ) -> Sequence[Task]:
        """Случайная выборка опубликованных задач темы (опц. фильтр по сложности)."""
        stmt = select(Task).where(
            Task.topic_id == topic_id,
            Task.status == TaskStatus.published,
        )
        if difficulty is not None:
            stmt = stmt.where(Task.difficulty == difficulty)
        stmt = stmt.order_by(func.random()).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def get_published(self, task_id: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.id == task_id, Task.status == TaskStatus.published)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def has_solved_correctly(self, *, user_id: uuid.UUID, task_id: uuid.UUID) -> bool:
        """Решал ли пользователь эту задачу верно раньше (для already_solved)."""
        stmt = select(Answer.id).where(
            Answer.user_id == user_id,
            Answer.task_id == task_id,
            Answer.is_correct.is_(True),
        )
        return (await self._session.execute(stmt.limit(1))).first() is not None

    async def record_answer(
        self,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        is_correct: bool,
        time_ms: int,
        submitted_at: datetime,
    ) -> Answer:
        answer = Answer(
            duel_id=None,
            user_id=user_id,
            task_id=task_id,
            is_correct=is_correct,
            time_ms=time_ms,
            submitted_at=submitted_at,
        )
        self._session.add(answer)
        await self._session.flush()
        return answer
