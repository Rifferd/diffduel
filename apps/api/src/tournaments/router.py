"""HTTP-роутер турниров (публичный список/детали + auth enter/tasks/answer).

- GET  /tournaments            — список (публичный, фильтр по статусу)
- GET  /tournaments/{id}       — детали + лидерборд (публичный, без N+1)
- POST /tournaments/{id}/enter — вход (auth; платёж-заглушка / бесплатно)
- GET  /tournaments/{id}/tasks — задачи турнира без эталонов (auth, участник)
- POST /tournaments/{id}/answer — ответ (auth, участник, active)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, rate_limit_user
from src.core.db import get_db
from src.core.enums import TournamentStatus
from src.tournaments.schemas import (
    EnterResult,
    TournamentAnswerResult,
    TournamentAnswerSubmit,
    TournamentDetail,
    TournamentSummary,
    TournamentTasks,
)
from src.tournaments.service import TournamentService
from src.users.models import User

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentSummary])
async def list_tournaments(
    status: TournamentStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[TournamentSummary]:
    return await TournamentService(session).list_tournaments(status=status)


@router.get("/{tournament_id}", response_model=TournamentDetail)
async def tournament_detail(
    tournament_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> TournamentDetail:
    return await TournamentService(session).detail(tournament_id)


@router.post("/{tournament_id}/enter", response_model=EnterResult)
async def enter_tournament(
    tournament_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EnterResult:
    return await TournamentService(session).enter(
        tournament_id=tournament_id, user_id=current_user.id
    )


@router.get("/{tournament_id}/tasks", response_model=TournamentTasks)
async def tournament_tasks(
    tournament_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TournamentTasks:
    return await TournamentService(session).tasks(
        tournament_id=tournament_id, user_id=current_user.id
    )


@router.post(
    "/{tournament_id}/answer",
    response_model=TournamentAnswerResult,
    dependencies=[Depends(rate_limit_user("tournament_answer", limit=60, window_s=60))],
)
async def answer_tournament(
    tournament_id: uuid.UUID,
    data: TournamentAnswerSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TournamentAnswerResult:
    return await TournamentService(session).submit(
        tournament_id=tournament_id, user_id=current_user.id, data=data
    )
