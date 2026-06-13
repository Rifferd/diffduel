"""Работа с refresh-cookie: имя, выставление, очистка."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Response

from src.core.config import get_settings

REFRESH_COOKIE_NAME = "dd_refresh"
# path=/ — куки должна слаться и когда фронт ходит на /api/auth/* (в проде Traefik
# срезает префикс /api, а браузер хранит куку по реальному пути запроса). При path=/auth
# куки не доходили до /api/auth/refresh и refresh ломался. httpOnly+Secure+SameSite=Lax
# остаются — компрометация области минимальна.
_COOKIE_PATH = "/"

# Cookie sid верификации: связывает регистрацию с verify-link «на том же устройстве».
VERIFY_SID_COOKIE_NAME = "dd_verify_sid"
VERIFY_SID_TTL_S = 30 * 60  # 30 минут


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


def set_verify_sid_cookie(response: Response, sid: str) -> None:
    """httpOnly + Secure(в проде) + SameSite=Lax, path=/, TTL 30 мин."""
    settings = get_settings()
    response.set_cookie(
        key=VERIFY_SID_COOKIE_NAME,
        value=sid,
        max_age=VERIFY_SID_TTL_S,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
