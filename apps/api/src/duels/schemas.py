"""Pydantic-схемы дуэльных internal-эндпоинтов (контракт duels.md).

ВНИМАНИЕ: эталон задачи (tasks.answer) отдаётся ТОЛЬКО внутреннему сервису
в ответе POST /internal/duels — здесь это сознательно и допустимо.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import TaskType

# Длина строкового идентификатора причины ограничена контрактом.
FinishReason = Literal["completed", "opponent_left", "aborted"]


class CreateDuelRequest(BaseModel):
    """POST /internal/duels — запрос матчмейкера realtime."""

    topic: str = Field(min_length=1, max_length=64)
    player_a: uuid.UUID
    player_b: uuid.UUID


class DuelTask(BaseModel):
    """Задача дуэли С эталоном — только для внутреннего сервиса."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TaskType
    difficulty: int
    body: dict[str, object]
    answer: dict[str, object]
    time_limit_s: int = 30


class CreateDuelResponse(BaseModel):
    """201 — пакет задач с эталонами и текущие рейтинги игроков."""

    duel_id: uuid.UUID
    topic: str
    tasks: list[DuelTask]
    # ключ — строковый uuid игрока, значение — его Эло по теме.
    ratings: dict[str, int]


class AnswerInput(BaseModel):
    """Один ответ игрока в дуэли (присылает realtime)."""

    task_id: uuid.UUID
    selected: int | None = None
    time_ms: int | None = None
    correct: bool


class PlayerResults(BaseModel):
    """Результаты одного игрока — ровно 5 ответов по контракту дуэли."""

    answers: list[AnswerInput] = Field(min_length=1, max_length=5)


class FinishDuelRequest(BaseModel):
    """POST /internal/duels/{id}/finish."""

    finished_at: datetime
    # ключ — строковый uuid игрока (ровно два игрока).
    results: dict[str, PlayerResults]
    reason: FinishReason


class FinishDuelResponse(BaseModel):
    """200 — итог дуэли (идемпотентный)."""

    winner_id: uuid.UUID | None
    deltas: dict[str, int]
    elo: dict[str, int]
