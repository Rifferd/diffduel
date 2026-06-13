"""Бизнес-логика домена tasks: тренировочная выборка и проверка ответов."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import NotFoundError
from src.core.telemetry import measure_answer_check
from src.tasks.checker import check_answer
from src.tasks.repository import TaskRepository
from src.tasks.schemas import AnswerResult, AnswerSubmit
from src.topics.models import Task


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tasks = TaskRepository(session)

    async def training(
        self,
        *,
        topic_slug: str,
        difficulty: int | None,
        limit: int,
    ) -> Sequence[Task]:
        topic_id = await self._tasks.topic_id_by_slug(topic_slug)
        if topic_id is None:
            raise NotFoundError("Тема не найдена", code="topic_not_found")
        return await self._tasks.random_published(
            topic_id=topic_id,
            difficulty=difficulty,
            limit=limit,
        )

    async def submit_answer(self, *, user_id: uuid.UUID, data: AnswerSubmit) -> AnswerResult:
        task = await self._tasks.get_published(data.task_id)
        if task is None:
            raise NotFoundError("Задача не найдена", code="task_not_found")

        with measure_answer_check(mode="solo") as m:
            result = check_answer(task.type, task.answer, data.answer.model_dump())
            m.correct = result.correct

        # already_solved считаем ДО записи текущего ответа: решал ли верно РАНЬШЕ.
        already_solved = await self._tasks.has_solved_correctly(user_id=user_id, task_id=task.id)

        await self._tasks.record_answer(
            user_id=user_id,
            task_id=task.id,
            is_correct=result.correct,
            time_ms=data.time_ms,
            submitted_at=datetime.now(tz=UTC),
        )

        return AnswerResult(
            correct=result.correct,
            correct_option=result.correct_option,
            explanation=task.explanation or "",
            already_solved=already_solved,
        )
