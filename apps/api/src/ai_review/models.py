"""ORM-модель домена ai_review: ai_reviews (разбор дуэли, pk(duel_id,user_id))."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz_now
from src.core.enums import AiReviewStatus

ai_review_status_enum = ENUM(AiReviewStatus, name="ai_review_status", create_type=False)


class AiReview(Base):
    __tablename__ = "ai_reviews"
    __table_args__ = (PrimaryKeyConstraint("duel_id", "user_id", name="pk_ai_reviews"),)

    duel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("duels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AiReviewStatus] = mapped_column(ai_review_status_enum, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[timestamptz_now]
    updated_at: Mapped[timestamptz_now]
