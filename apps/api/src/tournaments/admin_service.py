"""Бизнес-логика админки турниров: CRUD, смена статуса, grant-entry, места.

Набор задач турнира — фиксированный список published-задач выбранной темы:
явный task_ids (валидируется: published + та же тема) или task_count случайных.
При переводе статуса в finished автоматически пересчитываются места RANK().
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import TournamentStatus
from src.core.errors import NotFoundError, ValidationError
from src.core.logging import get_logger
from src.tournaments.models import Tournament
from src.tournaments.repository import TournamentRepository
from src.tournaments.schemas import (
    AdminTournament,
    TournamentCreate,
    TournamentUpdate,
)

logger = get_logger("tournaments.admin")


class TournamentAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TournamentRepository(session)

    async def create(self, data: TournamentCreate) -> AdminTournament:
        task_ids = await self._resolve_task_ids(data)
        tournament = Tournament(
            title=data.title,
            topic_id=data.topic_id,
            entry_fee=data.entry_fee,
            prize_pool=data.prize_pool,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            task_ids=task_ids,
            status=data.status,
        )
        self._repo.add(tournament)
        await self._session.commit()
        logger.info("tournament_created", tournament_id=str(tournament.id))
        return AdminTournament.model_validate(tournament)

    async def update(self, tournament_id: uuid.UUID, data: TournamentUpdate) -> AdminTournament:
        tournament = await self._require(tournament_id)
        previous_status = tournament.status
        if data.title is not None:
            tournament.title = data.title
        if data.starts_at is not None:
            tournament.starts_at = data.starts_at
        if data.ends_at is not None:
            tournament.ends_at = data.ends_at
        if data.entry_fee is not None:
            tournament.entry_fee = data.entry_fee
        if data.prize_pool is not None:
            tournament.prize_pool = data.prize_pool
        if data.status is not None:
            tournament.status = data.status
        await self._session.commit()

        # Завершение турнира → автоматический пересчёт мест RANK().
        if (
            data.status == TournamentStatus.finished
            and previous_status != TournamentStatus.finished
        ):
            await self._repo.recompute_places(tournament_id)
            await self._session.commit()
            logger.info("tournament_finished", tournament_id=str(tournament_id))

        return AdminTournament.model_validate(tournament)

    async def get(self, tournament_id: uuid.UUID) -> AdminTournament:
        return AdminTournament.model_validate(await self._require(tournament_id))

    async def _resolve_task_ids(self, data: TournamentCreate) -> list[uuid.UUID]:
        """Явный список (валидируется) ИЛИ случайные task_count published-задач темы."""
        if data.task_ids:
            valid = await self._repo.validate_published_task_ids(data.topic_id, data.task_ids)
            if len(valid) != len(set(data.task_ids)):
                raise ValidationError(
                    "Некоторые задачи не опубликованы или не из этой темы",
                    code="invalid_task_ids",
                )
            # Сохраняем порядок, заданный админом.
            return list(dict.fromkeys(data.task_ids))

        count = data.task_count
        if count is None:
            raise ValidationError("Укажите task_ids или task_count", code="task_set_required")
        picked = await self._repo.published_task_ids_of_topic(data.topic_id, limit=count)
        if len(picked) < count:
            raise ValidationError(
                "Недостаточно опубликованных задач в теме", code="not_enough_tasks"
            )
        return picked

    async def _require(self, tournament_id: uuid.UUID) -> Tournament:
        tournament = await self._repo.get(tournament_id)
        if tournament is None:
            raise NotFoundError("Турнир не найден", code="tournament_not_found")
        return tournament
