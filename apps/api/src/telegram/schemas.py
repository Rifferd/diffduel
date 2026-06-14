"""Pydantic-схемы домена telegram."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class LinkCodeResponse(BaseModel):
    """Ответ POST /me/telegram/link-code.

    bot_url пуст (None), если TELEGRAM_BOT_USERNAME не сконфигурирован.
    """

    code: str
    bot_url: str | None = None


class RedeemRequest(BaseModel):
    """Тело POST /internal/telegram/redeem (вызывает бот)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    telegram_user_id: int = Field(gt=0)


class RedeemResponse(BaseModel):
    """Результат успешной привязки."""

    user_id: uuid.UUID
    username: str


class ResolveResponse(BaseModel):
    """Ответ GET /internal/telegram/user/{telegram_user_id}."""

    user_id: uuid.UUID
    username: str
    linked: bool
