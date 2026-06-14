"""Бизнес-логика домена telegram: одноразовые коды привязки, redeem, resolve.

Одноразовый код хранится в Redis: ключ ``tg:link:{code}`` → user_id, TTL 10 мин.
Redeem проверяет код, выполняет upsert telegram_accounts и удаляет код (одноразовость).
"""

from __future__ import annotations

import secrets
import uuid
from typing import cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.errors import BadRequestError, NotFoundError
from src.telegram.repository import TelegramRepository
from src.telegram.schemas import (
    LinkCodeResponse,
    RedeemRequest,
    RedeemResponse,
    ResolveResponse,
)
from src.users.repository import UserRepository

# TTL одноразового кода привязки — 10 минут.
_CODE_TTL_S = 600
# Длина кода (символы из безопасного алфавита, см. _ALPHABET): 8 символов.
_CODE_LEN = 8
# Без визуально неоднозначных символов (0/O, 1/I/l) — код вводят/читают люди.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _link_key(code: str) -> str:
    return f"tg:link:{code}"


def _gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


class TelegramService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._repo = TelegramRepository(session)
        self._users = UserRepository(session)

    async def create_link_code(self, user_id: uuid.UUID) -> LinkCodeResponse:
        """Генерит одноразовый код в Redis (TTL 10 мин) и собирает deep-link бота."""
        code = _gen_code()
        await self._redis.set(_link_key(code), str(user_id), ex=_CODE_TTL_S)

        username = get_settings().telegram_bot_username
        bot_url = f"https://t.me/{username}?start={code}" if username else None
        return LinkCodeResponse(code=code, bot_url=bot_url)

    async def redeem(self, data: RedeemRequest) -> RedeemResponse:
        """Бот меняет код на привязку: проверяет код, upsert, удаляет код. Иначе 400."""
        key = _link_key(data.code)
        # decode_responses=True → str; стабы шире (bytes | str), поэтому cast.
        raw_user_id = cast("str | None", await self._redis.get(key))
        if raw_user_id is None:
            raise BadRequestError("Код недействителен или истёк", code="invalid_link_code")

        try:
            user_id = uuid.UUID(raw_user_id)
        except ValueError as exc:  # повреждённое значение в Redis — трактуем как невалид
            await self._redis.delete(key)
            raise BadRequestError("Код недействителен", code="invalid_link_code") from exc

        user = await self._users.get_by_id(user_id)
        if user is None or user.banned_at is not None:
            await self._redis.delete(key)
            raise BadRequestError("Пользователь недоступен", code="invalid_link_code")

        await self._repo.upsert(user_id=user_id, telegram_user_id=data.telegram_user_id)
        await self._session.commit()
        # Удаляем код только после успешной привязки — одноразовость.
        await self._redis.delete(key)
        return RedeemResponse(user_id=user.id, username=user.username)

    async def resolve(self, telegram_user_id: int) -> ResolveResponse:
        """Резолвит пользователя по telegram_user_id. Не привязан/забанен → 404."""
        linked = await self._repo.resolve(telegram_user_id)
        if linked is None or linked.banned:
            raise NotFoundError("Telegram не привязан", code="telegram_not_linked")
        return ResolveResponse(user_id=linked.user_id, username=linked.username, linked=True)

    async def unlink(self, user_id: uuid.UUID) -> None:
        """Отвязывает Telegram текущего пользователя (idempotent)."""
        await self._repo.delete_for_user(user_id)
        await self._session.commit()
