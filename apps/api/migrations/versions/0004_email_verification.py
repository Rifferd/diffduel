"""email verification: users.email_verified + email_verifications table

users.email_verified boolean not null default false (бэкофилл существующих → true,
чтобы не залочить уже заведённых пользователей). Таблица email_verifications хранит
только sha256-хэши кода/link_token/sid и метаданные попыток/срока.

Revision ID: 0004_email_verification
Revises: 0003_feature_flags
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_email_verification"
down_revision: str | None = "0003_feature_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users.email_verified — новые строки false, существующие бэкофилл в true.
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute("UPDATE users SET email_verified = true")

    op.create_table(
        "email_verifications",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("link_token_hash", sa.String(), nullable=False),
        sa.Column("sid_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_email_verifications_user"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_email_verifications"),
    )
    # Поиск по link_token_hash (verify-link).
    op.create_index(
        "ix_email_verifications_link_token_hash",
        "email_verifications",
        ["link_token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_verifications_link_token_hash", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_column("users", "email_verified")
