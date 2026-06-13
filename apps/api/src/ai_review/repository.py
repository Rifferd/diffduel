"""Доступ к данным AI-разбора: ai_reviews + сборка review-data из дуэли."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_review.models import AiReview
from src.core.enums import AiReviewStatus
from src.duels.models import Answer, Duel
from src.topics.models import Task, Topic


class AiReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> AiReview | None:
        return await self._session.get(AiReview, (duel_id, user_id))

    async def create_pending(self, duel_id: uuid.UUID, user_id: uuid.UUID) -> AiReview | None:
        """Создаёт pending-запись идемпотентно (ON CONFLICT DO NOTHING).

        Возвращает созданную запись, либо None, если запись уже была
        (тогда вызывающий перечитывает существующую).
        """
        stmt = (
            pg_insert(AiReview)
            .values(duel_id=duel_id, user_id=user_id, status=AiReviewStatus.pending)
            .on_conflict_do_nothing(index_elements=["duel_id", "user_id"])
            .returning(AiReview.duel_id)
        )
        created = (await self._session.execute(stmt)).scalar_one_or_none() is not None
        await self._session.commit()
        if not created:
            return None
        return await self.get(duel_id, user_id)

    async def upsert_result(
        self,
        duel_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        status: AiReviewStatus,
        content: str | None,
        error: str | None,
    ) -> AiReview:
        """Записывает результат разбора идемпотентно (воркер). updated_at = now()."""
        stmt = (
            pg_insert(AiReview)
            .values(
                duel_id=duel_id,
                user_id=user_id,
                status=status,
                content=content,
                error=error,
            )
            .on_conflict_do_update(
                index_elements=["duel_id", "user_id"],
                set_={
                    "status": status,
                    "content": content,
                    "error": error,
                    "updated_at": func.now(),
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        review = await self.get(duel_id, user_id)
        assert review is not None  # noqa: S101 — только что записали
        return review

    async def get_duel(self, duel_id: uuid.UUID) -> Duel | None:
        return await self._session.get(Duel, duel_id)

    async def topic_slug(self, topic_id: uuid.UUID) -> str | None:
        stmt = select(Topic.slug).where(Topic.id == topic_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def player_answers(
        self, duel_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[tuple[Task, Answer]]:
        """Задачи дуэли (с эталоном) + ответы игрока. Только для internal."""
        stmt = (
            select(Task, Answer)
            .join(Answer, Answer.task_id == Task.id)
            .where(Answer.duel_id == duel_id, Answer.user_id == user_id)
            .order_by(Answer.id.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
