"""HTTP-роутер админки турниров (/admin/tournaments, RBAC moderator/admin).

CRUD турниров, смена статуса (PATCH), ручная выдача входа (заглушка оплаты),
пересчёт мест RANK() по запросу.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import require_role
from src.core.db import get_db
from src.core.enums import UserRole
from src.tournaments.admin_service import TournamentAdminService
from src.tournaments.schemas import (
    AdminTournament,
    EnterResult,
    GrantEntryRequest,
    TournamentCreate,
    TournamentUpdate,
)
from src.tournaments.service import TournamentService

# Управление турнирами — moderator + admin (как задачи в админке).
router = APIRouter(
    prefix="/admin/tournaments",
    tags=["admin", "tournaments"],
    dependencies=[Depends(require_role(UserRole.moderator, UserRole.admin))],
)


@router.post("", response_model=AdminTournament, status_code=201)
async def create_tournament(
    data: TournamentCreate,
    session: AsyncSession = Depends(get_db),
) -> AdminTournament:
    return await TournamentAdminService(session).create(data)


@router.get("/{tournament_id}", response_model=AdminTournament)
async def get_tournament(
    tournament_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AdminTournament:
    return await TournamentAdminService(session).get(tournament_id)


@router.patch("/{tournament_id}", response_model=AdminTournament)
async def update_tournament(
    tournament_id: uuid.UUID,
    data: TournamentUpdate,
    session: AsyncSession = Depends(get_db),
) -> AdminTournament:
    return await TournamentAdminService(session).update(tournament_id, data)


@router.post("/{tournament_id}/grant-entry", response_model=EnterResult)
async def grant_entry(
    tournament_id: uuid.UUID,
    data: GrantEntryRequest,
    session: AsyncSession = Depends(get_db),
) -> EnterResult:
    """Ручная выдача входа (заглушка оплаты)."""
    return await TournamentService(session).grant_entry(
        tournament_id=tournament_id, user_id=data.user_id
    )


@router.post("/{tournament_id}/recompute-places", status_code=204)
async def recompute_places(
    tournament_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Пересчёт мест RANK() по запросу (помимо авто-пересчёта при finished)."""
    await TournamentService(session).recompute_places(tournament_id)
