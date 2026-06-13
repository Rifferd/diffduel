"""daily_challenges table (дневной челлендж)

daily_challenges(challenge_date date pk, task_id uuid fk→tasks, created_at).
Одна запись на дату — задача дня выбирается лениво и фиксируется ON CONFLICT.

Revision ID: 0005_daily_challenges
Revises: 0004_email_verification
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_daily_challenges"
down_revision: str | None = "0004_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_challenges",
        sa.Column("challenge_date", sa.Date(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="RESTRICT", name="fk_daily_challenges_task"
        ),
        sa.PrimaryKeyConstraint("challenge_date", name="pk_daily_challenges"),
    )


def downgrade() -> None:
    op.drop_table("daily_challenges")
