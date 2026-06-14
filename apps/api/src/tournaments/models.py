"""ORM-модели домена tournaments: tournaments, tournament_entries.

Таблицы созданы в 0001, расширены в 0007 (topic_id, ends_at, task_ids,
status enum; для entries — time_ms, finished_at).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz, uuid_pk
from src.core.enums import TournamentStatus

tournament_status_enum = ENUM(TournamentStatus, name="tournament_status", create_type=False)


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[uuid_pk]
    title: Mapped[str] = mapped_column(String, nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), nullable=True
    )
    entry_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    prize_pool: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    starts_at: Mapped[timestamptz]
    ends_at: Mapped[timestamptz | None] = mapped_column(nullable=True)
    # Фиксированный набор задач турнира (порядок значим).
    task_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=text("'{}'::uuid[]"), nullable=False
    )
    status: Mapped[TournamentStatus] = mapped_column(
        tournament_status_enum, server_default=text("'upcoming'"), nullable=False
    )


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
    time_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    place: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at: Mapped[timestamptz | None] = mapped_column(nullable=True)


class TournamentAnswer(Base):
    """Зачтённые ответы турнира — гарантия «один зачётный ответ на задачу».

    Уникальность (tournament_id, user_id, task_id) делает зачёт идемпотентным:
    повторный ответ на ту же задачу не добавляет score (ON CONFLICT DO NOTHING).
    Решение сверх спеки: отдельная таблица, а не флаг — выдерживает гонки и даёт
    точный набор уже зачтённых задач для определения завершения entry.
    """

    __tablename__ = "tournament_answers"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True
    )
