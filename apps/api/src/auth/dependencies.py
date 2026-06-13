"""FastAPI-зависимости auth: get_current_user по Bearer access-токену."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.enums import UserRole
from src.core.errors import AuthError, ForbiddenError
from src.core.rate_limit import check_rate_limit
from src.core.redis import get_redis
from src.core.security import decode_access_token
from src.users.models import User
from src.users.repository import UserRepository

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Достаёт пользователя по валидному access-JWT. Иначе 401."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Требуется авторизация", code="unauthorized")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthError("Невалидный токен", code="invalid_token") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthError("Пользователь не найден", code="invalid_token")
    if user.banned_at is not None:
        raise AuthError("Аккаунт заблокирован", code="account_banned")

    # Кладём в request.state для rate_limit(key="user").
    request.state.user = user
    return user


def require_role(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """RBAC-зависимость поверх get_current_user.

    Возвращает пользователя, если его роль входит в ``roles``; иначе 403.
    401 (нет/битый токен, бан) отдаётся раньше — это решает get_current_user.
    """
    allowed = set(roles)

    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise ForbiddenError("Недостаточно прав", code="forbidden")
        return current_user

    return _dependency


def rate_limit_user(name: str, limit: int, window_s: int) -> Callable[..., Awaitable[None]]:
    """Per-user rate limit, привязанный к авторизованному пользователю.

    В отличие от rate_limit(key="user"), явно зависит от get_current_user —
    это гарантирует, что 401 отдаётся раньше лимита, а identity всегда = user.id
    (никакого фоллбэка на IP для приватных эндпоинтов).
    """

    async def _dependency(
        current_user: User = Depends(get_current_user),
        redis: Redis = Depends(get_redis),
    ) -> None:
        await check_rate_limit(
            redis,
            name=name,
            identity=str(current_user.id),
            limit=limit,
            window_s=window_s,
        )

    return _dependency
