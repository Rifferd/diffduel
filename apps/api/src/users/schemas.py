"""Pydantic-схемы домена users."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from src.core.avatars import avatar_url
from src.core.enums import UserRole

_USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,30}$")

# Белый список content-type аватара → расширение ключа.
AVATAR_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_AVATAR_SIZE_BYTES = 2_097_152  # 2 МБ


def validate_username(value: str) -> str:
    """username: 3-30 символов [a-z0-9_-], case-insensitive (приводим к lower)."""
    normalized = value.strip().lower()
    if not _USERNAME_RE.match(normalized):
        raise ValueError("username должен быть 3-30 символов из [a-z0-9_-]")
    return normalized


class UserPublic(BaseModel):
    """Публичный профиль (без чувствительных полей)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    avatar_key: str | None
    role: UserRole
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avatar_url(self) -> str | None:
        """Публичный URL аватара: S3_PUBLIC_BASE_URL/avatars/{key}."""
        return avatar_url(self.avatar_key)


class UserMe(UserPublic):
    """Профиль для самого пользователя — добавляем email и Pro-статус."""

    email: str
    is_pro: bool = False


class TopicRating(BaseModel):
    """Эло пользователя по одной теме (для публичного профиля)."""

    slug: str
    title: str
    elo: int


class UserProfile(BaseModel):
    """Публичный профиль GET /users/{username} — без чувствительных полей."""

    username: str
    avatar_url: str | None
    created_at: datetime
    is_pro: bool
    topics: list[TopicRating]
    total_duels: int
    wins: int
    win_rate: float
    streak: int


class TopicAccuracy(BaseModel):
    """Точность пользователя по одной теме за период (расширенная статистика)."""

    slug: str
    title: str
    answered: int
    correct: int
    accuracy: float
    avg_time_ms: int


class UserStats(BaseModel):
    """Расширенная статистика профиля (GET /me/stats) — Pro-функция.

    Полная версия (Pro): агрегаты точности по темам за period + total.
    Решение по не-Pro: пейволл 402 pro_required (см. router), урезанной версии
    не отдаём — это явная Pro-ценность (см. release2.md §A).
    """

    period_days: int
    total_answered: int
    total_correct: int
    overall_accuracy: float
    topics: list[TopicAccuracy]


class AvatarPresignRequest(BaseModel):
    """POST /me/avatar/presign — параметры будущей загрузки."""

    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(gt=0, le=MAX_AVATAR_SIZE_BYTES)


class AvatarPresignResponse(BaseModel):
    """Ответ presign: куда и как грузить аватар напрямую в MinIO."""

    upload_url: str
    key: str
    expires_in: int


class AvatarConfirmRequest(BaseModel):
    """POST /me/avatar/confirm — подтверждение загруженного объекта."""

    key: str = Field(min_length=1, max_length=512)


class UserUpdate(BaseModel):
    """PATCH /me — изменяемые поля."""

    username: str | None = Field(default=None)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_username(value)
