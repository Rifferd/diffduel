"""Pydantic-схемы домена users."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.enums import UserRole

_USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,30}$")


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


class UserMe(UserPublic):
    """Профиль для самого пользователя — добавляем email."""

    email: str


class UserUpdate(BaseModel):
    """PATCH /me — изменяемые поля."""

    username: str | None = Field(default=None)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_username(value)
