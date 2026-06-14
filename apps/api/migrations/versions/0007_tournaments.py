"""tournaments: расширение модели турниров (Релиз 3, часть A)

Дополняет существующие таблицы из 0001:
- tournaments: topic_id (fk), ends_at, task_ids (uuid[]),
  status → enum tournament_status (upcoming|active|finished).
- tournament_entries: time_ms, finished_at.

Revision ID: 0007_tournaments
Revises: 0006_ai_reviews
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_tournaments"
down_revision: str | None = "0006_ai_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_ENUM = "tournament_status"


def upgrade() -> None:
    tournament_status = postgresql.ENUM(
        "upcoming", "active", "finished", name=_STATUS_ENUM, create_type=True
    )
    tournament_status.create(op.get_bind(), checkfirst=True)

    # --- tournaments ---------------------------------------------------------
    op.add_column(
        "tournaments",
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tournaments_topic",
        "tournaments",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "tournaments",
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tournaments",
        sa.Column(
            "task_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
    )
    # status был String — конвертируем в enum через USING.
    op.execute(
        "ALTER TABLE tournaments "
        "ALTER COLUMN status TYPE tournament_status "
        "USING status::tournament_status"
    )
    op.alter_column(
        "tournaments",
        "status",
        server_default=sa.text("'upcoming'::tournament_status"),
    )

    # --- tournament_entries --------------------------------------------------
    op.add_column(
        "tournament_entries",
        sa.Column("time_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "tournament_entries",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- tournament_answers (один зачётный ответ на задачу) ------------------
    op.create_table(
        "tournament_answers",
        sa.Column("tournament_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("tournament_id", "user_id", "task_id"),
    )


def downgrade() -> None:
    op.drop_table("tournament_answers")
    op.drop_column("tournament_entries", "finished_at")
    op.drop_column("tournament_entries", "time_ms")

    op.alter_column("tournaments", "status", server_default=None)
    op.execute("ALTER TABLE tournaments ALTER COLUMN status TYPE varchar USING status::varchar")
    op.drop_column("tournaments", "task_ids")
    op.drop_column("tournaments", "ends_at")
    op.drop_constraint("fk_tournaments_topic", "tournaments", type_="foreignkey")
    op.drop_column("tournaments", "topic_id")

    postgresql.ENUM(name=_STATUS_ENUM).drop(op.get_bind(), checkfirst=True)
