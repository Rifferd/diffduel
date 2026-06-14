"""Доступ к данным домена telegram: telegram_accounts.

Никакой бизнес-логики — только доступ к данным (conventions §Слои).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.telegram.models import TelegramAccount
from src.users.models import User


@dataclass(slots=True, frozen=True)
class LinkedUser:
    """Карточка пользователя, привязанного к Telegram."""

    user_id: uuid.UUID
    username: str
    banned: bool


class TelegramRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, *, user_id: uuid.UUID, telegram_user_id: int) -> None:
        """Привязывает Telegram к пользователю (idempotent upsert по user_id).

        Повторный link того же пользователя обновляет telegram_user_id; при
        переезде telegram_user_id на другого пользователя ON CONFLICT по PK
        не сработает — поэтому сначала снимаем чужую привязку этого tg-id.
        """
        # Снимаем привязку этого telegram_user_id с любого другого пользователя.
        await self._session.execute(
            delete(TelegramAccount).where(
                TelegramAccount.telegram_user_id == telegram_user_id,
                TelegramAccount.user_id != user_id,
            )
        )
        stmt = (
            pg_insert(TelegramAccount)
            .values(user_id=user_id, telegram_user_id=telegram_user_id)
            .on_conflict_do_update(
                index_elements=[TelegramAccount.user_id],
                set_={"telegram_user_id": telegram_user_id},
            )
        )
        await self._session.execute(stmt)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(TelegramAccount).where(TelegramAccount.user_id == user_id)
        )

    async def resolve(self, telegram_user_id: int) -> LinkedUser | None:
        """Находит привязанного пользователя по telegram_user_id (с ником и баном)."""
        stmt = (
            select(User.id, User.username, User.banned_at)
            .join(TelegramAccount, TelegramAccount.user_id == User.id)
            .where(TelegramAccount.telegram_user_id == telegram_user_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return LinkedUser(
            user_id=row.id,
            username=row.username,
            banned=row.banned_at is not None,
        )
