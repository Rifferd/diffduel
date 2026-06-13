"""Pydantic-схемы billing (admin grant/revoke Pro)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GrantProRequest(BaseModel):
    """POST /admin/users/{id}/grant-pro — продлить Pro на N дней."""

    days: int = Field(ge=1, le=3650)


class ProStatus(BaseModel):
    """Результат grant/revoke: текущее состояние подписки пользователя."""

    is_pro: bool
    current_period_end: datetime | None
