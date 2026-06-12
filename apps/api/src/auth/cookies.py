"""Работа с refresh-cookie: имя, выставление, очистка."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Response

from src.core.config import get_settings

REFRESH_COOKIE_NAME = "dd_refresh"
_COOKIE_PATH = "/auth"


def set_refresh_cookie(response: Response, token: str, *, expires_at: datetime) -> None:
    """httpOnly + Secure(в проде) + SameSite=Lax, path=/auth."""
    settings = get_settings()
    max_age = max(0, int((expires_at - datetime.now(tz=UTC)).total_seconds()))
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        samesite="lax",
    )
