"""Доступ к данным домена users."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User


class UserRepository:
    """Репозиторий пользователей. Никакой бизнес-логики — только доступ к данным."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def exists_email(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email)
        return (await self._session.execute(stmt)).first() is not None

    async def exists_username(self, username: str) -> bool:
        stmt = select(User.id).where(User.username == username)
        return (await self._session.execute(stmt)).first() is not None

    async def create(self, *, email: str, username: str, password_hash: str) -> User:
        user = User(email=email, username=username, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_username(self, user: User, username: str) -> User:
        user.username = username
        await self._session.flush()
        return user
