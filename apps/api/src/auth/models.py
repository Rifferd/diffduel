"""ORM-модели домена auth: oauth_accounts, refresh_tokens."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz, timestamptz_now, uuid_pk
from src.core.enums import OAuthProvider

oauth_provider_enum = ENUM(OAuthProvider, name="oauth_provider", create_type=False)


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[OAuthProvider] = mapped_column(oauth_provider_enum, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[timestamptz_now]


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Семья токенов: reuse detection отзывает всю family_id.
    family_id: Mapped[uuid.UUID] = mapped_column(
        index=True, server_default=text("gen_random_uuid()"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    expires_at: Mapped[timestamptz]
    rotated_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
    revoked_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
    created_at: Mapped[timestamptz_now]


class EmailVerification(Base):
    """Незавершённая верификация email. Хранит только хэши, не сам код/токен.

    PK = user_id (одна активная верификация на пользователя; resend перезаписывает).
    """

    __tablename__ = "email_verifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    link_token_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sid_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[timestamptz]
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    sent_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
