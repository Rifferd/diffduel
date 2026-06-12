"""ORM-модели домена topics: topics, tasks, task_stats."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import uuid_pk
from src.core.enums import TaskStatus, TaskType

task_type_enum = ENUM(TaskType, name="task_type", create_type=False)
task_status_enum = ENUM(TaskStatus, name="task_status", create_type=False)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid_pk]
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_topic_difficulty_status", "topic_id", "difficulty", "status"),
        # GIN по тэгам внутри body->'tags'.
        Index(
            "ix_tasks_body_tags_gin",
            text("(body -> 'tags')"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid_pk]
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False
    )
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[TaskType] = mapped_column(task_type_enum, nullable=False)
    body: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    # answer — эталон, НИКОГДА не сериализуется в публичные схемы.
    answer: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        task_status_enum, server_default=text("'draft'"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)


class TaskStat(Base):
    __tablename__ = "task_stats"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    shown: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    solved: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    avg_time_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    p50_time_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
