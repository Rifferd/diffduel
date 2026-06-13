"""ai_reviews table (AI-разбор ошибок дуэли, Pro-функция)

ai_reviews(duel_id uuid, user_id uuid, status enum('pending','done','failed'),
content text null, error text null, created_at, updated_at, pk(duel_id, user_id)).
Идемпотентность разбора — по составному ключу (duel_id, user_id).

Revision ID: 0006_ai_reviews
Revises: 0005_daily_challenges
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_ai_reviews"
down_revision: str | None = "0005_daily_challenges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ai_review_status = postgresql.ENUM("pending", "done", "failed", name="ai_review_status")
    ai_review_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_reviews",
        sa.Column("duel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "done", "failed", name="ai_review_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["duel_id"], ["duels.id"], ondelete="CASCADE", name="fk_ai_reviews_duel"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_ai_reviews_user"
        ),
        sa.PrimaryKeyConstraint("duel_id", "user_id", name="pk_ai_reviews"),
    )


def downgrade() -> None:
    op.drop_table("ai_reviews")
    postgresql.ENUM(name="ai_review_status").drop(op.get_bind(), checkfirst=True)
