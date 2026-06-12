"""PG-native enum'ы доменной модели (см. ТЗ §5)."""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    user = "user"
    moderator = "moderator"
    admin = "admin"


class OAuthProvider(enum.StrEnum):
    github = "github"
    google = "google"


class TaskType(enum.StrEnum):
    quiz = "quiz"
    code_bug = "code_bug"
    sql = "sql"
    design = "design"


class TaskStatus(enum.StrEnum):
    draft = "draft"
    review = "review"
    published = "published"


class DuelStatus(enum.StrEnum):
    matched = "matched"
    running = "running"
    finished = "finished"
    aborted = "aborted"


class SubscriptionPlan(enum.StrEnum):
    pro = "pro"


class PaymentPurpose(enum.StrEnum):
    subscription = "subscription"
    tournament_entry = "tournament_entry"
    ai_review = "ai_review"
