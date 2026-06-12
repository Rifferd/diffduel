"""Доступ к данным refresh-токенов (с поддержкой ротации и family-revoke)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        family_id: uuid.UUID | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        if family_id is not None:
            token.family_id = family_id
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def claim_for_rotation(self, token_id: uuid.UUID, *, now: datetime) -> bool:
        """Атомарно помечает токен ротированным.

        Гонка двух параллельных /auth/refresh одним токеном: оба проходят
        SELECT, но UPDATE с предикатом выигрывает только один. Проигравший
        получает False — это reuse.
        """
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.id == token_id,
                RefreshToken.rotated_at.is_(None),
                RefreshToken.revoked_at.is_(None),
            )
            .values(rotated_at=now)
            .returning(RefreshToken.id)
        )
        claimed = (await self._session.execute(stmt)).scalar_one_or_none()
        return claimed is not None

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime) -> None:
        """Отзывает все ещё не отозванные токены семьи (reuse detection / logout)."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.execute(stmt)
