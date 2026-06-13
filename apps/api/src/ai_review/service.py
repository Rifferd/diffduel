"""Бизнес-логика AI-разбора дуэли.

Поток:
- POST /ai/review/{duel_id}: проверки (участник, дуэль finished), идемпотентно
  создаём pending и продюсируем событие ``ai.review.requested``; если запись уже
  pending/done — возвращаем её без повторного события.
- воркер тянет данные через internal GET review-data (эталоны не утекают
  публично) и пишет результат через internal POST.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_review.models import AiReview
from src.ai_review.repository import AiReviewRepository
from src.ai_review.schemas import (
    AiReviewResponse,
    ReviewDataResponse,
    ReviewTaskData,
    WriteReviewRequest,
)
from src.core import events
from src.core.enums import AiReviewStatus, DuelStatus
from src.core.errors import ForbiddenError, NotFoundError, ValidationError
from src.core.logging import get_logger
from src.duels.models import Answer
from src.topics.models import Task

logger = get_logger("ai_review")

_TOPIC = "ai.review.requested"


class AiReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AiReviewRepository(session)

    # --- публичные операции --------------------------------------------------

    async def request(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> AiReviewResponse:
        """Запрашивает разбор. Идемпотентно: pending/done — возвращаем как есть."""
        await self._ensure_participant_finished(duel_id, user_id)

        existing = await self._repo.get(duel_id, user_id)
        if existing is not None and existing.status in (
            AiReviewStatus.pending,
            AiReviewStatus.done,
        ):
            return _to_response(existing)

        created = await self._repo.create_pending(duel_id, user_id)
        if created is None:
            # Гонка: конкурентный запрос успел создать запись — отдаём её.
            current = await self._repo.get(duel_id, user_id)
            if current is not None:
                return _to_response(current)
            # Крайне маловероятно (failed мог быть удалён) — пересоздаём pending.
            created = await self._repo.create_pending(duel_id, user_id)
            if created is None:
                current = await self._repo.get(duel_id, user_id)
                assert current is not None  # noqa: S101
                return _to_response(current)

        await events.produce(
            _TOPIC,
            key=str(duel_id),
            event_type="ai.review.requested",
            payload={"duel_id": str(duel_id), "user_id": str(user_id)},
        )
        logger.info("ai_review_requested", duel_id=str(duel_id), user_id=str(user_id))
        return _to_response(created)

    async def get(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> AiReviewResponse:
        """Текущий статус разбора (auth, участник)."""
        await self._ensure_participant_finished(duel_id, user_id)
        review = await self._repo.get(duel_id, user_id)
        if review is None:
            raise NotFoundError("Разбор не запрашивался", code="ai_review_not_found")
        return _to_response(review)

    # --- internal операции ---------------------------------------------------

    async def write_result(
        self, duel_id: uuid.UUID, user_id: uuid.UUID, data: WriteReviewRequest
    ) -> AiReviewResponse:
        """Воркер пишет результат разбора (идемпотентно по (duel_id,user_id))."""
        review = await self._repo.upsert_result(
            duel_id,
            user_id,
            status=data.status,
            content=data.content,
            error=data.error,
        )
        return _to_response(review)

    async def review_data(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> ReviewDataResponse:
        """Данные для разбора (вопросы+эталоны+ответы игрока) — ТОЛЬКО internal."""
        duel = await self._repo.get_duel(duel_id)
        if duel is None:
            raise NotFoundError("Дуэль не найдена", code="duel_not_found")
        if user_id not in (duel.player_a, duel.player_b):
            raise ForbiddenError("Игрок не участник дуэли", code="not_participant")

        slug = await self._repo.topic_slug(duel.topic_id)
        rows = await self._repo.player_answers(duel_id, user_id)
        tasks = [
            ReviewTaskData(
                task_id=task.id,
                type=str(task.type),
                body=task.body,
                answer=task.answer,
                explanation=task.explanation,
                selected=_selected(task, answer),
                is_correct=answer.is_correct,
                time_ms=answer.time_ms,
            )
            for task, answer in rows
        ]
        return ReviewDataResponse(
            duel_id=duel_id,
            user_id=user_id,
            topic=slug or "",
            tasks=tasks,
        )

    # --- внутреннее ----------------------------------------------------------

    async def _ensure_participant_finished(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        duel = await self._repo.get_duel(duel_id)
        if duel is None:
            raise NotFoundError("Дуэль не найдена", code="duel_not_found")
        if user_id not in (duel.player_a, duel.player_b):
            raise ForbiddenError("Вы не участник этой дуэли", code="not_participant")
        if duel.status != DuelStatus.finished:
            raise ValidationError(
                "Разбор доступен только для завершённой дуэли", code="not_finished"
            )


def _selected(task: Task, answer: Answer) -> int | None:
    """Что выбрал игрок: для is_correct=true это эталон, иначе неизвестно.

    answers не хранит выбранный вариант (selected) — только корректность.
    Для верного ответа выбор совпадает с эталоном задачи; для неверного — None
    (фактический выбор не сохраняется в БД, см. duels.service).
    """
    if not answer.is_correct:
        return None
    correct = task.answer.get("correct")
    return correct if isinstance(correct, int) else None


def _to_response(review: AiReview) -> AiReviewResponse:
    return AiReviewResponse(status=review.status, content=review.content, error=review.error)
