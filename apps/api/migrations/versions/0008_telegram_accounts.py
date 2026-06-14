"""telegram_accounts: привязка Telegram-аккаунта к пользователю (Релиз 3, часть A)

Таблица telegram_accounts:
- user_id pk fk→users (ON DELETE CASCADE) — один Telegram на пользователя.
- telegram_user_id bigint unique — id пользователя в Telegram.
- linked_at — момент привязки.

Revision ID: 0008_telegram_accounts
Revises: 0007_tournaments
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_telegram_accounts"
down_revision: str | None = "0007_tournaments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_accounts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_accounts_tg_user_id"),
    )


def downgrade() -> None:
    op.drop_table("telegram_accounts")
