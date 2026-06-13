"""Pydantic-схемы админки.

Задачи в админке ВКЛЮЧАЮТ answer/explanation — это закрытый RBAC-роутер для
модераторов/админов, а не публичная схема (контракт: tasks.answer не попадает
только в ПУБЛИЧНЫЕ схемы).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import TaskStatus, TaskType

# --- Tasks -------------------------------------------------------------------


class AdminTask(BaseModel):
    """Задача в админке — с эталоном (закрытый роутер)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    difficulty: int
    type: TaskType
    body: dict[str, object]
    answer: dict[str, object]
    explanation: str | None
    status: TaskStatus
    author_id: uuid.UUID | None
    version: int


class AdminTaskList(BaseModel):
    """Страница задач."""

    items: list[AdminTask]
    page: int
    page_size: int
    total: int


class TaskCreate(BaseModel):
    """POST /admin/tasks — создание (всегда стартует в draft)."""

    topic_id: uuid.UUID
    difficulty: int = Field(ge=1, le=5)
    type: TaskType
    body: dict[str, object]
    answer: dict[str, object]
    explanation: str | None = Field(default=None, max_length=4000)


class TaskUpdate(BaseModel):
    """PATCH /admin/tasks/{id} — частичное обновление редактируемых полей."""

    difficulty: int | None = Field(default=None, ge=1, le=5)
    body: dict[str, object] | None = None
    answer: dict[str, object] | None = None
    explanation: str | None = Field(default=None, max_length=4000)


# --- Users -------------------------------------------------------------------


class AdminUser(BaseModel):
    """Пользователь в админке."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    role: str
    created_at: datetime
    banned_at: datetime | None


class AdminUserList(BaseModel):
    items: list[AdminUser]
    page: int
    page_size: int
    total: int


class BanRequest(BaseModel):
    """POST /admin/users/{id}/ban — причина бана (журналируется)."""

    reason: str = Field(min_length=1, max_length=500)


# --- Metrics -----------------------------------------------------------------


class MetricsOverview(BaseModel):
    users: int
    duels_24h: int
    duels_7d: int
    published_tasks: int
    active_subscriptions: int


# --- Feature flags -----------------------------------------------------------


class FeatureFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    enabled: bool
    payload: dict[str, object] | None
    updated_at: datetime


class FeatureFlagUpsert(BaseModel):
    """PUT /admin/feature-flags/{key}."""

    enabled: bool
    payload: dict[str, object] | None = None
