"""FastAPI-зависимости auth: get_current_user по Bearer access-токену."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.errors import AuthError
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
