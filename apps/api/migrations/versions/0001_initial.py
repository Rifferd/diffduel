"""initial schema: расширения, enum'ы, все таблицы ТЗ §5, партиции answers.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Расширения ----------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # для gen_random_uuid()

    # --- Native enum'ы -------------------------------------------------------
    user_role = postgresql.ENUM("user", "moderator", "admin", name="user_role")
    oauth_provider = postgresql.ENUM("github", "google", name="oauth_provider")
    task_type = postgresql.ENUM("quiz", "code_bug", "sql", "design", name="task_type")
    task_status = postgresql.ENUM("draft", "review", "published", name="task_status")
    duel_status = postgresql.ENUM("matched", "running", "finished", "aborted", name="duel_status")
    subscription_plan = postgresql.ENUM("pro", name="subscription_plan")
    payment_purpose = postgresql.ENUM(
        "subscription", "tournament_entry", "ai_review", name="payment_purpose"
    )
    bind = op.get_bind()
    for enum_type in (
        user_role,
        oauth_provider,
        task_type,
        task_status,
        duel_status,
        subscription_plan,
        payment_purpose,
    ):
        enum_type.create(bind, checkfirst=True)

    uuid_pk = sa.text("gen_random_uuid()")

    # --- users ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("username", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("avatar_key", sa.String(), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(name="user_role", create_type=False),
            server_default=sa.text("'user'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    # --- topics --------------------------------------------------------------
    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_topics_slug"),
    )

    # --- oauth_accounts ------------------------------------------------------
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider", postgresql.ENUM(name="oauth_provider", create_type=False), nullable=False
        ),
        sa.Column("provider_user_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    # --- refresh_tokens ------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "family_id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False
        ),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # --- tasks ---------------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("type", postgresql.ENUM(name="task_type", create_type=False), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="task_status", create_type=False),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tasks_topic_difficulty_status", "tasks", ["topic_id", "difficulty", "status"]
    )
    op.execute("CREATE INDEX ix_tasks_body_tags_gin ON tasks USING gin ((body -> 'tags'))")

    # --- task_stats ----------------------------------------------------------
    op.create_table(
        "task_stats",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shown", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("solved", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_time_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("p50_time_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id"),
    )

    # --- duels ---------------------------------------------------------------
    op.create_table(
        "duels",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", postgresql.ENUM(name="duel_status", create_type=False), nullable=False),
        sa.Column("player_a", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_b", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("winner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rating_delta_a", sa.Integer(), nullable=True),
        sa.Column("rating_delta_b", sa.Integer(), nullable=True),
        sa.Column("share_card_key", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_a"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_b"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- ratings -------------------------------------------------------------
    op.create_table(
        "ratings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("elo", sa.Integer(), server_default=sa.text("1200"), nullable=False),
        sa.Column("games", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("wins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("streak", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "topic_id"),
    )

    # --- subscriptions -------------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "plan", postgresql.ENUM(name="subscription_plan", create_type=False), nullable=False
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_sub_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # --- payments ------------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column(
            "purpose", postgresql.ENUM(name="payment_purpose", create_type=False), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id", name="uq_payments_provider_event_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    # --- tournaments ---------------------------------------------------------
    op.create_table(
        "tournaments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=uuid_pk, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("entry_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("prize_pool", sa.Numeric(10, 2), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tournament_entries",
        sa.Column("tournament_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("place", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tournament_id", "user_id"),
        sa.UniqueConstraint("tournament_id", "user_id", name="uq_tournament_entry"),
    )

    # --- answers (партиционированная по месяцам) -----------------------------
    op.execute(
        """
        CREATE TABLE answers (
            id bigint GENERATED BY DEFAULT AS IDENTITY,
            duel_id uuid NULL REFERENCES duels(id) ON DELETE SET NULL,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
            is_correct boolean NOT NULL,
            time_ms integer NOT NULL,
            submitted_at timestamptz NOT NULL,
            CONSTRAINT pk_answers PRIMARY KEY (id, submitted_at)
        ) PARTITION BY RANGE (submitted_at)
        """
    )
    op.create_index("ix_answers_user_id", "answers", ["user_id"])
    op.create_index("ix_answers_duel_id", "answers", ["duel_id"])

    # Функция-helper: идемпотентно создаёт месячную партицию по дате.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_answers_partition(p_month date)
        RETURNS void AS $$
        DECLARE
            start_date date := date_trunc('month', p_month)::date;
            end_date   date := (date_trunc('month', p_month) + interval '1 month')::date;
            part_name  text := 'answers_' || to_char(start_date, 'YYYY_MM');
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = part_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF answers FOR VALUES FROM (%L) TO (%L)',
                    part_name, start_date, end_date
                );
            END IF;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    # Партиции на текущий и следующий месяц.
    op.execute("SELECT create_answers_partition(now()::date)")
    op.execute(
        "SELECT create_answers_partition((date_trunc('month', now()) + interval '1 month')::date)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS answers CASCADE")
    op.execute("DROP FUNCTION IF EXISTS create_answers_partition(date)")
    op.drop_table("tournament_entries")
    op.drop_table("tournaments")
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_table("ratings")
    op.drop_table("duels")
    op.drop_table("task_stats")
    op.drop_table("tasks")
    op.drop_table("refresh_tokens")
    op.drop_table("oauth_accounts")
    op.drop_table("topics")
    op.drop_table("users")
    for enum_name in (
        "payment_purpose",
        "subscription_plan",
        "duel_status",
        "task_status",
        "task_type",
        "oauth_provider",
        "user_role",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
