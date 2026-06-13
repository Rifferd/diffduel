"""ORM-модель feature_flags (админка)."""

from __future__ import annotations

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz_now, uuid_pk


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[uuid_pk]
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[timestamptz_now]
    updated_at: Mapped[timestamptz_now]
