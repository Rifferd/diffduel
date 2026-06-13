"""ORM-модель домена daily: daily_challenges (одна задача на дату)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz_now


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    challenge_date: Mapped[date] = mapped_column(Date, primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[timestamptz_now]
