"""Бизнес-логика админки: задачи (пайплайн draft→review→published),
пользователи (бан/разбан), метрики, фиче-флаги (с инвалидацией кэша)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin import flags_cache
from src.admin.repository import AdminRepository
from src.admin.schemas import (
    AdminTask,
    AdminTaskList,
    AdminUser,
    AdminUserList,
    BanRequest,
    FeatureFlagOut,
    FeatureFlagUpsert,
    MetricsOverview,
    TaskCreate,
    TaskUpdate,
)
from src.core.enums import TaskStatus, TaskType
from src.core.errors import ConflictError, NotFoundError, ValidationError
from src.core.logging import get_logger
from src.topics.models import Task

logger = get_logger("admin")

# Допустимые переходы статуса задачи.
_PUBLISH_FROM = {TaskStatus.draft, TaskStatus.review}


class AdminService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._repo = AdminRepository(session)

    # --- Tasks ---------------------------------------------------------------

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None,
        topic_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> AdminTaskList:
        items, total = await self._repo.list_tasks(
            status=status, topic_id=topic_id, limit=page_size, offset=(page - 1) * page_size
        )
        return AdminTaskList(
            items=[AdminTask.model_validate(t) for t in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def create_task(self, data: TaskCreate, *, author_id: uuid.UUID) -> AdminTask:
        if not await self._repo.topic_exists(data.topic_id):
            raise NotFoundError("Тема не найдена", code="topic_not_found")
        # Контент валидируем уже на создании — мусор не должен копиться в draft.
        _validate_task_content(data.type, data.body, data.answer)
        task = Task(
            topic_id=data.topic_id,
            difficulty=data.difficulty,
            type=data.type,
            body=data.body,
            answer=data.answer,
            explanation=data.explanation,
            status=TaskStatus.draft,
            author_id=author_id,
        )
        task = await self._repo.add_task(task)
        await self._session.commit()
        return AdminTask.model_validate(task)

    async def update_task(self, task_id: uuid.UUID, data: TaskUpdate) -> AdminTask:
        task = await self._require_task(task_id)
        if task.status == TaskStatus.published:
            raise ConflictError("Опубликованную задачу нельзя редактировать", code="task_published")
        if data.difficulty is not None:
            task.difficulty = data.difficulty
        if data.body is not None:
            task.body = data.body
        if data.answer is not None:
            task.answer = data.answer
        if data.explanation is not None:
            task.explanation = data.explanation
        # Перепроверяем итоговый контент.
        _validate_task_content(task.type, task.body, task.answer)
        await self._session.commit()
        return AdminTask.model_validate(task)

    async def publish_task(self, task_id: uuid.UUID) -> AdminTask:
        task = await self._require_task(task_id)
        if task.status == TaskStatus.published:
            raise ConflictError("Задача уже опубликована", code="task_already_published")
        if task.status not in _PUBLISH_FROM:
            raise ConflictError("Недопустимый переход статуса", code="invalid_transition")
        # Гейт публикации: контент обязан проходить чекер по типу.
        _validate_task_content(task.type, task.body, task.answer)
        task.status = TaskStatus.published
        await self._session.commit()
        logger.info("task_published", task_id=str(task.id))
        return AdminTask.model_validate(task)

    async def reject_task(self, task_id: uuid.UUID) -> AdminTask:
        """Отклонение: возврат в draft (review→draft)."""
        task = await self._require_task(task_id)
        if task.status == TaskStatus.published:
            raise ConflictError("Опубликованную задачу нельзя отклонить", code="task_published")
        task.status = TaskStatus.draft
        await self._session.commit()
        return AdminTask.model_validate(task)

    async def _require_task(self, task_id: uuid.UUID) -> Task:
        task = await self._repo.get_task(task_id)
        if task is None:
            raise NotFoundError("Задача не найдена", code="task_not_found")
        return task

    # --- Users ---------------------------------------------------------------

    async def list_users(self, *, q: str | None, page: int, page_size: int) -> AdminUserList:
        items, total = await self._repo.list_users(
            q=q, limit=page_size, offset=(page - 1) * page_size
        )
        return AdminUserList(
            items=[AdminUser.model_validate(u) for u in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def ban_user(self, user_id: uuid.UUID, data: BanRequest) -> AdminUser:
        user = await self._repo.get_user(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден", code="user_not_found")
        await self._repo.set_banned_at(user, datetime.now(tz=UTC))
        await self._session.commit()
        logger.info("user_banned", user_id=str(user.id), reason=data.reason)
        return AdminUser.model_validate(user)

    async def unban_user(self, user_id: uuid.UUID) -> AdminUser:
        user = await self._repo.get_user(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден", code="user_not_found")
        await self._repo.set_banned_at(user, None)
        await self._session.commit()
        logger.info("user_unbanned", user_id=str(user.id))
        return AdminUser.model_validate(user)

    # --- Metrics -------------------------------------------------------------

    async def metrics_overview(self) -> MetricsOverview:
        now = datetime.now(tz=UTC)
        return MetricsOverview(
            users=await self._repo.count_users(),
            duels_24h=await self._repo.count_duels_since(now - timedelta(hours=24)),
            duels_7d=await self._repo.count_duels_since(now - timedelta(days=7)),
            published_tasks=await self._repo.count_published_tasks(),
            active_subscriptions=await self._repo.count_active_subscriptions(),
        )

    # --- Feature flags -------------------------------------------------------

    async def list_flags(self) -> list[FeatureFlagOut]:
        flags = await self._repo.list_flags()
        return [FeatureFlagOut.model_validate(f) for f in flags]

    async def upsert_flag(self, key: str, data: FeatureFlagUpsert) -> FeatureFlagOut:
        flag = await self._repo.upsert_flag(
            key=key,
            enabled=data.enabled,
            payload=data.payload,
            now=datetime.now(tz=UTC),
        )
        await self._session.commit()
        # Инвалидируем кэш — следующее чтение возьмёт свежее значение.
        await flags_cache.invalidate(self._redis, key)
        logger.info("feature_flag_upserted", key=key, enabled=data.enabled)
        return FeatureFlagOut.model_validate(flag)


def _validate_task_content(
    task_type: TaskType, body: dict[str, object], answer: dict[str, object]
) -> None:
    """Валидация body/answer по типу через checker-подход (quiz: options≥2, correct в диапазоне)."""
    if task_type == TaskType.quiz:
        options = body.get("options")
        if not isinstance(options, list) or len(options) < 2:
            raise ValidationError("quiz: требуется не менее 2 опций", code="invalid_task_body")
        correct = answer.get("correct")
        if not isinstance(correct, int) or isinstance(correct, bool):
            raise ValidationError(
                "quiz: answer.correct должен быть int", code="invalid_task_answer"
            )
        if not 0 <= correct < len(options):
            raise ValidationError(
                "quiz: answer.correct вне диапазона опций", code="invalid_task_answer"
            )
        return
    # Прочие типы пока без публикации (как и checker — unsupported).
    raise ValidationError(
        f"Публикация задач типа {task_type} пока не поддерживается",
        code="unsupported_task_type",
    )
