"""ORM-модель домена telegram: telegram_accounts."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz_now


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    linked_at: Mapped[timestamptz_now]
