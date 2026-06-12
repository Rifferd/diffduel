"""Бизнес-логика auth: регистрация, логин, ротация refresh, reuse detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.repository import RefreshTokenRepository
from src.auth.schemas import LoginRequest, RegisterRequest
from src.core.config import get_settings
from src.core.errors import AuthError, ConflictError
from src.core.logging import get_logger
from src.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from src.users.models import User
from src.users.repository import UserRepository

logger = get_logger("auth")


@dataclass(slots=True)
class IssuedTokens:
    """Результат выпуска пары токенов."""

    access_token: str
    access_expires_in: int
    refresh_token: str  # сырой токен — только для записи в cookie, не логируется
    refresh_expires_at: datetime


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)
        self._settings = get_settings()

    # --- Регистрация / логин -------------------------------------------------

    async def register(self, data: RegisterRequest) -> User:
        if await self._users.exists_email(data.email):
            raise ConflictError("Email уже занят", code="email_taken")
        if await self._users.exists_username(data.username):
            raise ConflictError("Username уже занят", code="username_taken")
        try:
            user = await self._users.create(
                email=data.email,
                username=data.username,
                password_hash=hash_password(data.password),
            )
        except IntegrityError as exc:
            # Гонка между двумя параллельными регистрациями.
            raise ConflictError("Email или username уже занят", code="conflict") from exc
        logger.info("user_registered", user_id=str(user.id))
        return user

    async def authenticate(self, data: LoginRequest) -> User:
        """Аутентификация. Ответ не различает 'нет юзера' / 'не тот пароль'."""
        user = await self._users.get_by_email(data.email)
        # Всегда выполняем verify, чтобы не было таймингового оракула.
        password_hash = user.password_hash if user and user.password_hash else None
        if user is None or password_hash is None:
            # Тратим время на фейковую проверку (защита от user-enumeration по таймингу).
            verify_password(data.password, _DUMMY_HASH)
            raise AuthError("Неверный email или пароль", code="invalid_credentials")
        if not verify_password(data.password, password_hash):
            raise AuthError("Неверный email или пароль", code="invalid_credentials")
        if user.banned_at is not None:
            raise AuthError("Аккаунт заблокирован", code="account_banned")
        return user

    # --- Выпуск / ротация токенов -------------------------------------------

    async def issue_tokens(self, user: User, *, family_id: uuid.UUID | None = None) -> IssuedTokens:
        now = datetime.now(tz=UTC)
        access = create_access_token(user.id, now=now)
        refresh_raw = generate_refresh_token()
        refresh_expires = now + timedelta(seconds=self._settings.refresh_token_ttl)
        await self._tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_raw),
            expires_at=refresh_expires,
            family_id=family_id,
        )
        return IssuedTokens(
            access_token=access,
            access_expires_in=self._settings.access_token_ttl,
            refresh_token=refresh_raw,
            refresh_expires_at=refresh_expires,
        )

    async def login(self, data: LoginRequest) -> tuple[User, IssuedTokens]:
        user = await self.authenticate(data)
        tokens = await self.issue_tokens(user)
        logger.info("user_logged_in", user_id=str(user.id))
        return user, tokens

    async def refresh(self, raw_token: str) -> IssuedTokens:
        """Ротация: помечает старый rotated_at, выпускает новый в той же family.

        Reuse detection: приход уже-ротированного / отозванного / истёкшего токена
        отзывает ВСЮ family и возвращает 401.
        """
        now = datetime.now(tz=UTC)
        token = await self._tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is None:
            raise AuthError("Невалидный токен", code="invalid_refresh_token")

        # Reuse detection: токен уже отозван или уже ротирован → компрометация.
        if token.revoked_at is not None or token.rotated_at is not None:
            await self._revoke_family_durably(token.family_id, now=now)
            logger.warning(
                "refresh_reuse_detected",
                user_id=str(token.user_id),
                family_id=str(token.family_id),
            )
            raise AuthError("Токен скомпрометирован", code="invalid_refresh_token")

        if _aware(token.expires_at) <= now:
            await self._revoke_family_durably(token.family_id, now=now)
            raise AuthError("Токен истёк", code="invalid_refresh_token")

        user = await self._users.get_by_id(token.user_id)
        if user is None or user.banned_at is not None:
            await self._revoke_family_durably(token.family_id, now=now)
            raise AuthError("Невалидный токен", code="invalid_refresh_token")

        # Ротация в той же семье — строго атомарно: при гонке двух параллельных
        # refresh одним токеном проигравший трактуется как reuse.
        if not await self._tokens.claim_for_rotation(token.id, now=now):
            await self._revoke_family_durably(token.family_id, now=now)
            logger.warning(
                "refresh_reuse_detected_concurrent",
                user_id=str(token.user_id),
                family_id=str(token.family_id),
            )
            raise AuthError("Токен скомпрометирован", code="invalid_refresh_token")
        tokens = await self.issue_tokens(user, family_id=token.family_id)
        logger.info("token_refreshed", user_id=str(user.id))
        return tokens

    async def _revoke_family_durably(self, family_id: uuid.UUID, *, now: datetime) -> None:
        """Отзыв family + немедленный commit, чтобы он пережил последующий raise.

        get_db делает rollback при исключении, поэтому security-критичный отзыв
        фиксируем явно перед тем, как бросить 401.
        """
        await self._tokens.revoke_family(family_id, now=now)
        await self._session.commit()

    async def logout(self, raw_token: str | None) -> None:
        """Отзывает всю family токена (если он есть и валиден по форме)."""
        if not raw_token:
            return
        now = datetime.now(tz=UTC)
        token = await self._tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is not None:
            await self._tokens.revoke_family(token.family_id, now=now)
            logger.info("user_logged_out", user_id=str(token.user_id))


def _aware(value: datetime) -> datetime:
    """Гарантирует tz-aware datetime (asyncpg возвращает aware, sqlite — naive)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# Реальный argon2id-хэш фиксированного пароля для фейковой проверки при
# отсутствии пользователя — чтобы /auth/login не давал таймингового оракула.
_DUMMY_HASH = hash_password("dummy-password-for-timing-equalization")
