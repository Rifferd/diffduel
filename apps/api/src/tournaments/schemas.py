"""Pydantic-схемы домена tournaments.

Публичные схемы НИКОГДА не несут эталоны задач — задачи турнира отдаются как
TaskPublic (без answer/explanation), результат проверки — только в ответе на
POST /answer. Лидерборд обогащается никами батчем (без N+1).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import TournamentStatus
from src.tasks.schemas import AnswerPayload, TaskPublic

# Лимиты строк (валидация всех входов).
_TITLE_MAX = 200


class TournamentSummary(BaseModel):
    """Строка списка турниров."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    topic_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime | None
    entry_fee: Decimal
    prize_pool: Decimal
    status: TournamentStatus
    entries_count: int


class TournamentLeaderboardEntry(BaseModel):
    """Строка лидерборда турнира (обогащена ником/аватаром)."""

    user_id: uuid.UUID
    username: str
    avatar_url: str | None
    score: int
    time_ms: int
    place: int | None


class TournamentDetail(BaseModel):
    """GET /tournaments/{id} — детали + лидерборд."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    topic_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime | None
    entry_fee: Decimal
    prize_pool: Decimal
    status: TournamentStatus
    tasks_count: int
    entries_count: int
    leaderboard: list[TournamentLeaderboardEntry]


class EnterResult(BaseModel):
    """POST /tournaments/{id}/enter — результат входа."""

    joined: bool
    already_entered: bool


class TournamentAnswerSubmit(BaseModel):
    """POST /tournaments/{id}/answer — ответ на задачу турнира."""

    task_id: uuid.UUID
    answer: AnswerPayload
    time_ms: int = Field(ge=100, le=600_000)


class TournamentAnswerResult(BaseModel):
    """Результат проверки ответа турнира.

    ``scored`` — учтён ли ответ (один зачётный ответ на задачу).
    ``finished`` — закрыта ли вся entry (ответы на все задачи).
    """

    correct: bool
    correct_option: int
    explanation: str
    scored: bool
    already_answered: bool
    score: int
    finished: bool


# --- Admin -------------------------------------------------------------------


class TournamentCreate(BaseModel):
    """POST /admin/tournaments — создание турнира.

    Набор задач: либо явный список published-задач темы (``task_ids``), либо
    случайные ``task_count`` published-задач темы (если task_ids не задан).
    """

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    topic_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime | None = None
    entry_fee: Decimal = Field(ge=0, default=Decimal("0"))
    prize_pool: Decimal = Field(ge=0, default=Decimal("0"))
    task_count: int | None = Field(default=None, ge=1, le=50)
    task_ids: list[uuid.UUID] | None = None
    status: TournamentStatus = TournamentStatus.upcoming


class TournamentUpdate(BaseModel):
    """PATCH /admin/tournaments/{id} — частичное обновление."""

    title: str | None = Field(default=None, min_length=1, max_length=_TITLE_MAX)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    entry_fee: Decimal | None = Field(default=None, ge=0)
    prize_pool: Decimal | None = Field(default=None, ge=0)
    status: TournamentStatus | None = None


class GrantEntryRequest(BaseModel):
    """POST /admin/tournaments/{id}/grant-entry — ручная выдача входа."""

    user_id: uuid.UUID


class AdminTournament(BaseModel):
    """Полное представление турнира для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    topic_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime | None
    entry_fee: Decimal
    prize_pool: Decimal
    status: TournamentStatus
    task_ids: list[uuid.UUID]


class TournamentTasks(BaseModel):
    """GET /tournaments/{id}/tasks — задачи турнира без эталонов."""

    tasks: list[TaskPublic]
