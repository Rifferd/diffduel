"""Бизнес-логика домена users."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ConflictError
from src.users.models import User
from src.users.repository import UserRepository
from src.users.schemas import UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def update_me(self, user: User, data: UserUpdate) -> User:
        if data.username is not None and data.username != user.username:
            if await self._users.exists_username(data.username):
                raise ConflictError("Username уже занят", code="username_taken")
            try:
                await self._users.update_username(user, data.username)
            except IntegrityError as exc:
                raise ConflictError("Username уже занят", code="username_taken") from exc
        return user
