"""Pydantic-схемы домена tasks.

КЛЮЧЕВОЕ: публичные схемы НИКОГДА не несут tasks.answer / explanation.
Эталон ответа и объяснение отдаются ТОЛЬКО как результат проверки в POST /answers.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import TaskType


class QuizBody(BaseModel):
    """body для type=quiz (включая код-вопросы: сниппет в code)."""

    question: str
    options: list[str]
    code: str | None = None
    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class TaskPublic(BaseModel):
    """Публичная задача для тренировки — без answer и explanation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TaskType
    difficulty: int
    body: QuizBody


class AnswerSubmit(BaseModel):
    """POST /answers — ответ в соло-режиме."""

    task_id: uuid.UUID
    answer: AnswerPayload
    time_ms: int = Field(ge=100, le=600_000)


class AnswerPayload(BaseModel):
    """Полезная нагрузка ответа на quiz: индекс выбранной опции."""

    selected: int = Field(ge=0)


class AnswerResult(BaseModel):
    """Результат проверки ответа (соло-режим)."""

    correct: bool
    correct_option: int
    explanation: str
    already_solved: bool


AnswerSubmit.model_rebuild()
