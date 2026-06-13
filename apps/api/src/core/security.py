"""Криптопримитивы: argon2id-пароли, access-JWT (HS256), refresh-токены (sha256)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from src.core.config import get_settings

_JWT_ALG = "HS256"
_password_hasher = PasswordHasher()

# Размер refresh-токена: 256 бит энтропии.
_REFRESH_TOKEN_BYTES = 32


# --- Пароли (argon2id) -------------------------------------------------------


def hash_password(password: str) -> str:
    """Хэширует пароль argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против argon2id-хэша. Без утечки причины неуспеха."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Нужно ли перехэшировать (изменились параметры argon2)."""
    return _password_hasher.check_needs_rehash(password_hash)


# --- Access JWT (HS256) ------------------------------------------------------


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> str:
    """Выпускает access-JWT с claims sub/exp/iat/jti/type."""
    settings = get_settings()
    issued_at = now or datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(seconds=settings.access_token_ttl)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any]:
    """Декодирует и валидирует access-JWT. Бросает jwt.PyJWTError при ошибке."""
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[_JWT_ALG],
        options={"require": ["exp", "iat", "sub"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Refresh-токены ----------------------------------------------------------


def generate_refresh_token() -> str:
    """Криптослучайный refresh-токен (256 бит) в виде url-safe строки."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """sha256-хэш refresh-токена (в БД хранится только хэш)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sha256_hex(value: str) -> str:
    """sha256-hex произвольной строки (код/link_token/sid email-верификации)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# --- Constant-time сравнение -------------------------------------------------


def constant_time_equals(left: str, right: str) -> bool:
    """Сравнение строк без утечки времени (для внутренних токенов)."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
