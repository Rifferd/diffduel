"""profile stats indexes: duels(player_a), duels(player_b)

Витрина публичного профиля (GET /users/{username}) фильтрует завершённые дуэли
игрока по (player_a = uid OR player_b = uid). Btree-индексы по обеим колонкам
дают index scan вместо seq scan на duels (см. ADR-0002).

Revision ID: 0002_profile_indexes
Revises: 0001_initial
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_profile_indexes"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_duels_player_a", "duels", ["player_a"])
    op.create_index("ix_duels_player_b", "duels", ["player_b"])


def downgrade() -> None:
    op.drop_index("ix_duels_player_b", table_name="duels")
    op.drop_index("ix_duels_player_a", table_name="duels")
