"""ORM-модели домена tournaments: tournaments, tournament_entries."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz, uuid_pk


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[uuid_pk]
    title: Mapped[str] = mapped_column(String, nullable=False)
    entry_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    prize_pool: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    starts_at: Mapped[timestamptz]
    status: Mapped[str] = mapped_column(String, nullable=False)


class TournamentEntry(Base):
    __tablename__ = "tournament_entries"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id", name="uq_tournament_entry"),)

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    place: Mapped[int | None] = mapped_column(Integer, nullable=True)
