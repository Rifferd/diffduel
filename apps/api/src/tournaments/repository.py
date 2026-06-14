"""Доступ к данным домена tournaments.

Лидерборд турнира читается с обогащением никами одним батч-JOIN (без N+1):
tournament_entries JOIN users. Пересчёт мест — оконной функцией RANK() прямо в
SQL (UPDATE ... FROM подзапрос). Эталоны задач здесь не сериализуются — наружу
уходит только TaskPublic в сервисе.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import TaskStatus, TournamentStatus
from src.topics.models import Task
from src.tournaments.models import Tournament, TournamentAnswer, TournamentEntry
from src.users.models import User


@dataclass(slots=True, frozen=True)
class LeaderboardRow:
    """Строка лидерборда турнира (entry + ник игрока)."""

    user_id: uuid.UUID
    username: str
    avatar_key: str | None
    score: int
    time_ms: int
    place: int | None


class TournamentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Tournaments ---------------------------------------------------------

    async def list_tournaments(
        self, *, status: TournamentStatus | None
    ) -> list[tuple[Tournament, int]]:
        """Список турниров с числом участников (один запрос, без N+1)."""
        entries_count = (
            select(
                TournamentEntry.tournament_id.label("tid"),
                func.count().label("cnt"),
            )
            .group_by(TournamentEntry.tournament_id)
            .subquery()
        )
        stmt = (
            select(Tournament, func.coalesce(entries_count.c.cnt, 0))
            .outerjoin(entries_count, entries_count.c.tid == Tournament.id)
            .order_by(Tournament.starts_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Tournament.status == status)
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], int(row[1])) for row in rows]

    async def get(self, tournament_id: uuid.UUID) -> Tournament | None:
        stmt = select(Tournament).where(Tournament.id == tournament_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, tournament: Tournament) -> Tournament:
        self._session.add(tournament)
        return tournament

    # --- Tasks ---------------------------------------------------------------

    async def published_task_ids_of_topic(
        self, topic_id: uuid.UUID, *, limit: int | None = None
    ) -> list[uuid.UUID]:
        """published-задачи темы (случайный порядок; опц. лимит) — для набора турнира."""
        stmt = (
            select(Task.id)
            .where(Task.topic_id == topic_id, Task.status == TaskStatus.published)
            .order_by(func.random())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def validate_published_task_ids(
        self, topic_id: uuid.UUID, task_ids: Sequence[uuid.UUID]
    ) -> list[uuid.UUID]:
        """Возвращает из task_ids те, что published и принадлежат теме."""
        if not task_ids:
            return []
        stmt = select(Task.id).where(
            Task.id.in_(list(task_ids)),
            Task.topic_id == topic_id,
            Task.status == TaskStatus.published,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def tasks_public(self, task_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Task]:
        """Батч-загрузка задач турнира (для TaskPublic, без N+1)."""
        if not task_ids:
            return {}
        stmt = select(Task).where(Task.id.in_(list(task_ids)))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {task.id: task for task in rows}

    async def get_task(self, task_id: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.id == task_id, Task.status == TaskStatus.published)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # --- Entries -------------------------------------------------------------

    async def get_entry(
        self, tournament_id: uuid.UUID, user_id: uuid.UUID
    ) -> TournamentEntry | None:
        stmt = select(TournamentEntry).where(
            TournamentEntry.tournament_id == tournament_id,
            TournamentEntry.user_id == user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_entry_if_absent(self, tournament_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """INSERT ... ON CONFLICT DO NOTHING. True, если строка вставлена."""
        stmt = (
            pg_insert(TournamentEntry)
            .values(tournament_id=tournament_id, user_id=user_id, score=0, time_ms=0)
            .on_conflict_do_nothing(index_elements=["tournament_id", "user_id"])
            .returning(TournamentEntry.user_id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        return inserted is not None

    async def leaderboard(self, tournament_id: uuid.UUID) -> list[LeaderboardRow]:
        """Лидерборд турнира одним JOIN (без N+1). Забаненных не светим."""
        stmt = (
            select(
                TournamentEntry.user_id,
                User.username,
                User.avatar_key,
                TournamentEntry.score,
                TournamentEntry.time_ms,
                TournamentEntry.place,
            )
            .join(User, User.id == TournamentEntry.user_id)
            .where(
                TournamentEntry.tournament_id == tournament_id,
                User.banned_at.is_(None),
            )
            .order_by(
                func.coalesce(TournamentEntry.score, 0).desc(),
                TournamentEntry.time_ms.asc(),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            LeaderboardRow(
                user_id=row.user_id,
                username=row.username,
                avatar_key=row.avatar_key,
                score=int(row.score or 0),
                time_ms=int(row.time_ms),
                place=row.place,
            )
            for row in rows
        ]

    async def answered_task_ids(
        self, tournament_id: uuid.UUID, user_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """Задачи, по которым у игрока уже зачтён ответ в этом турнире.

        Источник истины зачёта — таблица tournament_answers (один зачёт/задачу).
        """
        stmt = select(TournamentAnswer.task_id).where(
            TournamentAnswer.tournament_id == tournament_id,
            TournamentAnswer.user_id == user_id,
        )
        return set((await self._session.execute(stmt)).scalars().all())

    async def record_scored_answer(
        self,
        *,
        tournament_id: uuid.UUID,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> bool:
        """Фиксирует зачётный ответ на задачу (один на задачу). True, если зачтён.

        Гонка параллельных ответов на одну задачу: ON CONFLICT DO NOTHING —
        зачёт получает только первый.
        """
        stmt = (
            pg_insert(TournamentAnswer)
            .values(tournament_id=tournament_id, user_id=user_id, task_id=task_id)
            .on_conflict_do_nothing(index_elements=["tournament_id", "user_id", "task_id"])
            .returning(TournamentAnswer.task_id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        return inserted is not None

    async def add_entry_score(
        self,
        *,
        tournament_id: uuid.UUID,
        user_id: uuid.UUID,
        add_score: int,
        add_time_ms: int,
        finished_at: datetime | None,
    ) -> TournamentEntry:
        """Атомарно накапливает score/time в entry; опц. ставит finished_at."""
        values: dict[str, object] = {
            "score": func.coalesce(TournamentEntry.score, 0) + add_score,
            "time_ms": TournamentEntry.time_ms + add_time_ms,
        }
        if finished_at is not None:
            values["finished_at"] = finished_at
        stmt = (
            update(TournamentEntry)
            .where(
                TournamentEntry.tournament_id == tournament_id,
                TournamentEntry.user_id == user_id,
            )
            .values(**values)
            .returning(TournamentEntry)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def recompute_places(self, tournament_id: uuid.UUID) -> None:
        """Пересчёт мест: RANK() OVER (ORDER BY score DESC, time_ms ASC).

        Raw SQL с параметром — оконные функции в UPDATE ... FROM выразительнее
        в чистом SQL; tournament_id передаётся параметром (без инъекций).
        """
        await self._session.execute(
            text(
                """
                UPDATE tournament_entries te
                SET place = ranked.rnk
                FROM (
                    SELECT user_id,
                           RANK() OVER (
                               ORDER BY COALESCE(score, 0) DESC, time_ms ASC
                           ) AS rnk
                    FROM tournament_entries
                    WHERE tournament_id = :tid
                ) AS ranked
                WHERE te.tournament_id = :tid
                  AND te.user_id = ranked.user_id
                """
            ),
            {"tid": tournament_id},
        )
