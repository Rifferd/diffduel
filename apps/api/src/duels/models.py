"""ORM-модели домена duels: duels, answers (партиционированная)."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz, uuid_pk
from src.core.enums import DuelStatus

duel_status_enum = ENUM(DuelStatus, name="duel_status", create_type=False)


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[uuid_pk]
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[DuelStatus] = mapped_column(duel_status_enum, nullable=False)
    player_a: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    player_b: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
    finished_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
    rating_delta_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_delta_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_card_key: Mapped[str | None] = mapped_column(String, nullable=True)


class Answer(Base):
    """answers — самая горячая таблица, PARTITION BY RANGE (submitted_at).

    Сама таблица и партиции создаются в Alembic-миграции (raw DDL),
    т.к. SQLAlchemy DDL не описывает партиционирование декларативно.
    Модель нужна для ORM-доступа и типов.
    """

    __tablename__ = "answers"
    __table_args__ = (
        # PK включает ключ партиционирования — требование PG.
        PrimaryKeyConstraint("id", "submitted_at", name="pk_answers"),
        {"postgresql_partition_by": "RANGE (submitted_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    duel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("duels.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[timestamptz]
