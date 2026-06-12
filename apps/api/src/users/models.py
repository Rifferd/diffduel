"""ORM-модели домена users: users, ratings."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import citext, timestamptz, timestamptz_now, uuid_pk
from src.core.enums import UserRole

user_role_enum = ENUM(UserRole, name="user_role", create_type=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[citext] = mapped_column(unique=True)
    username: Mapped[citext] = mapped_column(unique=True)
    # password_hash NULL — для пользователей, заведённых только через OAuth.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, server_default=text("'user'"), nullable=False
    )
    created_at: Mapped[timestamptz_now]
    banned_at: Mapped[timestamptz | None] = mapped_column(nullable=True)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_ratings_user_topic"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    elo: Mapped[int] = mapped_column(Integer, server_default=text("1200"), nullable=False)
    games: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    wins: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    streak: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
