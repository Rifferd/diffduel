"""Авторизация внутренних эндпоинтов по заголовку X-Internal-Token."""

from __future__ import annotations

from fastapi import Header

from src.core.config import get_settings
from src.core.errors import AuthError
from src.core.security import constant_time_equals


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    """Constant-time сравнение с INTERNAL_API_TOKEN. Иначе 401."""
    settings = get_settings()
    if x_internal_token is None or not constant_time_equals(
        x_internal_token, settings.internal_api_token
    ):
        raise AuthError("Недействительный внутренний токен", code="unauthorized")
