"""Pydantic-схемы AI-разбора дуэли.

ВНИМАНИЕ: эталоны задач (correct/explanation) присутствуют ТОЛЬКО в
:class:`ReviewDataResponse` — это ответ INTERNAL-эндпоинта воркеру.
Публичные схемы (status/content/error) эталонов не содержат.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from src.core.enums import AiReviewStatus


class AiReviewResponse(BaseModel):
    """Публичный статус разбора (POST/GET /ai/review/{duel_id})."""

    status: AiReviewStatus
    content: str | None = None
    error: str | None = None


class WriteReviewRequest(BaseModel):
    """POST /internal/ai-reviews/{duel_id}/{user_id} — воркер пишет результат."""

    status: AiReviewStatus
    content: str | None = Field(default=None, max_length=20_000)
    error: str | None = Field(default=None, max_length=2_000)


class ReviewTaskData(BaseModel):
    """Задача дуэли с эталоном и ответом игрока — ТОЛЬКО для воркера."""

    task_id: uuid.UUID
    type: str
    body: dict[str, object]
    # Эталон задачи (tasks.answer) — никогда в публичных схемах.
    answer: dict[str, object]
    explanation: str | None = None
    # Что выбрал игрок (None — не ответил), верно ли, время.
    selected: int | None = None
    is_correct: bool = False
    time_ms: int | None = None


class ReviewDataResponse(BaseModel):
    """GET /internal/duels/{id}/review-data — данные для разбора игрока."""

    duel_id: uuid.UUID
    user_id: uuid.UUID
    topic: str
    tasks: list[ReviewTaskData]
