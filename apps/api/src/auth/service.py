"""Бизнес-логика auth: регистрация, логин, ротация refresh, reuse detection."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.repository import EmailVerificationRepository, RefreshTokenRepository
from src.auth.schemas import LoginRequest, RegisterRequest
from src.core.config import get_settings
from src.core.email import send_verification_email
from src.core.errors import AuthError, BadRequestError, ConflictError
from src.core.logging import get_logger
from src.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    sha256_hex,
    verify_password,
)
from src.users.models import User
from src.users.repository import UserRepository

logger = get_logger("auth")

_VERIFICATION_TTL = timedelta(minutes=15)
_MAX_ATTEMPTS = 5
_RESEND_THROTTLE = timedelta(seconds=60)


@dataclass(slots=True)
class IssuedTokens:
    """Результат выпуска пары токенов."""

    access_token: str
    access_expires_in: int
    refresh_token: str  # сырой токен — только для записи в cookie, не логируется
    refresh_expires_at: datetime


@dataclass(slots=True)
class RegisterResult:
    """Итог регистрации. ON-режим возвращает sid для cookie вместо токенов."""

    verification_required: bool
    tokens: IssuedTokens | None = None
    verify_sid: str | None = None


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)
        self._verifications = EmailVerificationRepository(session)
        self._settings = get_settings()

    # --- Регистрация / логин -------------------------------------------------

    async def register(self, data: RegisterRequest) -> RegisterResult:
        verification_required = self._settings.email_verification_enabled
        if await self._users.exists_email(data.email):
            raise ConflictError("Email уже занят", code="email_taken")
        if await self._users.exists_username(data.username):
            raise ConflictError("Username уже занят", code="username_taken")
        try:
            user = await self._users.create(
                email=data.email,
                username=data.username,
                password_hash=hash_password(data.password),
                email_verified=not verification_required,
            )
        except IntegrityError as exc:
            # Гонка между двумя параллельными регистрациями.
            raise ConflictError("Email или username уже занят", code="conflict") from exc
        logger.info("user_registered", user_id=str(user.id))

        if not verification_required:
            tokens = await self.issue_tokens(user)
            return RegisterResult(verification_required=False, tokens=tokens)

        sid = await self._issue_verification(user)
        return RegisterResult(verification_required=True, verify_sid=sid)

    async def _issue_verification(self, user: User) -> str:
        """Генерит код+link_token+sid, сохраняет хэши, шлёт письмо. Возвращает sid."""
        now = datetime.now(tz=UTC)
        code = f"{secrets.randbelow(1_000_000):06d}"
        link_token = secrets.token_urlsafe(32)
        sid = secrets.token_urlsafe(32)
        await self._verifications.upsert(
            user_id=user.id,
            code_hash=sha256_hex(code),
            link_token_hash=sha256_hex(link_token),
            sid_hash=sha256_hex(sid),
            expires_at=now + _VERIFICATION_TTL,
            sent_at=now,
        )
        # Письмо шлём ПОСЛЕ записи кода в БД: при провале SMTP (503) код уже
        # доступен через resend. commit фиксируем сразу — переживёт raise 503.
        await self._session.commit()
        link_url = f"{self._settings.public_web_url}/verify?token={link_token}"
        await send_verification_email(user.email, code, link_url)
        return sid

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
        if not user.email_verified:
            raise AuthError(
                "Почта не подтверждена",
                code="email_not_verified",
                status_code=403,
            )
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

    # --- Подтверждение email -------------------------------------------------

    async def verify_email(self, email: str, code: str) -> IssuedTokens:
        """Код-путь подтверждения. Успех → email_verified + токены (авто-логин).

        Не различает 'нет юзера' / 'нет кода' / 'не тот код' (общий invalid_code),
        кроме истечения и исчерпания попыток.
        """
        now = datetime.now(tz=UTC)
        user = await self._users.get_by_email(email)
        verification = (
            await self._verifications.get_by_user_id(user.id) if user is not None else None
        )
        if user is None or verification is None:
            raise BadRequestError("Неверный код", code="invalid_code")

        if verification.attempts >= _MAX_ATTEMPTS:
            await self._verifications.delete(user.id)
            await self._session.commit()
            raise BadRequestError("Слишком много попыток", code="too_many_attempts")

        if _aware(verification.expires_at) <= now:
            raise BadRequestError("Код истёк", code="code_expired")

        if not secrets.compare_digest(verification.code_hash, sha256_hex(code)):
            new_attempts = await self._verifications.increment_attempts(user.id)
            await self._session.commit()
            if new_attempts >= _MAX_ATTEMPTS:
                await self._verifications.delete(user.id)
                await self._session.commit()
                raise BadRequestError("Слишком много попыток", code="too_many_attempts")
            raise BadRequestError("Неверный код", code="invalid_code")

        await self._users.mark_email_verified(user)
        await self._verifications.delete(user.id)
        tokens = await self.issue_tokens(user)
        logger.info("email_verified_by_code", user_id=str(user.id))
        return tokens

    async def verify_link(self, token: str, *, sid: str | None) -> tuple[bool, IssuedTokens | None]:
        """Ссылочный путь. Возвращает (logged_in, tokens|None).

        Подтверждает email идемпотентно. Если cookie dd_verify_sid совпала с
        записью — авто-логин (то же устройство). Иначе — только подтверждение:
        код в БД лежит хэшем, показать его неоткуда; пользователь вводит код из
        письма на устройстве регистрации.
        """
        now = datetime.now(tz=UTC)
        verification = await self._verifications.get_by_link_token_hash(sha256_hex(token))
        if verification is None:
            raise BadRequestError("Невалидная ссылка", code="invalid_token")
        if _aware(verification.expires_at) <= now:
            raise BadRequestError("Ссылка истекла", code="token_expired")

        user = await self._users.get_by_id(verification.user_id)
        if user is None:
            raise BadRequestError("Невалидная ссылка", code="invalid_token")

        await self._users.mark_email_verified(user)

        same_device = sid is not None and secrets.compare_digest(
            verification.sid_hash, sha256_hex(sid)
        )
        if same_device:
            await self._verifications.delete(user.id)
            tokens = await self.issue_tokens(user)
            logger.info("email_verified_by_link_same_device", user_id=str(user.id))
            return True, tokens

        # Другое устройство: email подтверждён, запись оставляем — на устройстве
        # регистрации пользователь ещё введёт код (verify-email) для логина.
        logger.info("email_verified_by_link_other_device", user_id=str(user.id))
        return False, None

    async def resend_code(self, email: str) -> None:
        """Перегенерит код+link_token, шлёт письмо. Всегда без раскрытия статуса.

        Троттлинг не чаще 1/60с на email (по sent_at). SMTP-провал → 503.
        """
        now = datetime.now(tz=UTC)
        user = await self._users.get_by_email(email)
        if user is None or user.email_verified:
            return
        existing = await self._verifications.get_by_user_id(user.id)
        if existing is not None and existing.sent_at is not None:
            if now - _aware(existing.sent_at) < _RESEND_THROTTLE:
                # Тихо игнорируем (не раскрываем существование/статус).
                return
        await self._issue_verification(user)

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
