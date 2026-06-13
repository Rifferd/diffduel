"""Pydantic-схемы домена daily.

Публичная задача дня — без эталона (переиспользуем TaskPublic из tasks).
Лидерборд — никами без N+1 (переиспользуем форму leaderboard).
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from src.tasks.schemas import AnswerPayload, TaskPublic


class DailyTask(BaseModel):
    """GET /daily — задача дня (без эталона)."""

    challenge_date: date
    task: TaskPublic


class DailyAnswerSubmit(BaseModel):
    """POST /daily/answer — ответ на задачу дня."""

    answer: AnswerPayload
    time_ms: int = Field(ge=100, le=600_000)


class DailyAnswerResult(BaseModel):
    """Результат проверки дневного ответа.

    ``scored`` — учтён ли ответ в лидерборде (только первый зачётный за день).
    ``already_answered`` — был ли зачётный ответ ранее сегодня.
    """

    correct: bool
    correct_option: int
    explanation: str
    scored: bool
    already_answered: bool


class DailyLeaderboardEntry(BaseModel):
    """Строка дневного лидерборда (обогащена ником/аватаром)."""

    rank: int
    user_id: uuid.UUID
    username: str
    avatar_url: str | None
    score: int


class DailyMyPosition(BaseModel):
    """GET /daily/me — моя позиция в дневном лидерборде."""

    rank: int | None
    score: int | None
