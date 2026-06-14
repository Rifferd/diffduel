"""Внутренний роутер /internal/* — НЕ публикуется в OpenAPI."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_review.schemas import AiReviewResponse, ReviewDataResponse, WriteReviewRequest
from src.ai_review.service import AiReviewService
from src.core.db import get_db
from src.core.redis import get_redis
from src.duels.schemas import (
    CreateDuelRequest,
    CreateDuelResponse,
    DuelCardResponse,
    FinishDuelRequest,
    FinishDuelResponse,
    SetShareCardRequest,
)
from src.duels.service import DuelService
from src.internal_api.dependencies import require_internal_token
from src.telegram.schemas import RedeemRequest, RedeemResponse, ResolveResponse
from src.telegram.service import TelegramService

# include_in_schema=False на каждом маршруте — чтобы не попасть в публичный OpenAPI.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_token)],
)


@router.get("/ping", include_in_schema=False)
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/duels",
    response_model=CreateDuelResponse,
    status_code=201,
    include_in_schema=False,
)
async def create_duel(
    data: CreateDuelRequest,
    session: AsyncSession = Depends(get_db),
) -> CreateDuelResponse:
    return await DuelService(session).create(data)


@router.post(
    "/duels/{duel_id}/finish",
    response_model=FinishDuelResponse,
    include_in_schema=False,
)
async def finish_duel(
    duel_id: uuid.UUID,
    data: FinishDuelRequest,
    session: AsyncSession = Depends(get_db),
) -> FinishDuelResponse:
    return await DuelService(session).finish(duel_id, data)


@router.get(
    "/duels/{duel_id}/card",
    response_model=DuelCardResponse,
    include_in_schema=False,
)
async def get_duel_card(
    duel_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DuelCardResponse:
    return await DuelService(session).get_card(duel_id)


@router.post(
    "/duels/{duel_id}/share-card",
    status_code=204,
    include_in_schema=False,
)
async def set_duel_share_card(
    duel_id: uuid.UUID,
    data: SetShareCardRequest,
    session: AsyncSession = Depends(get_db),
) -> None:
    await DuelService(session).set_share_card(duel_id, data.key)


# --- AI-разбор (ai-review воркер) --------------------------------------------


@router.get(
    "/duels/{duel_id}/review-data",
    response_model=ReviewDataResponse,
    include_in_schema=False,
)
async def get_review_data(
    duel_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReviewDataResponse:
    return await AiReviewService(session).review_data(duel_id, user_id)


@router.post(
    "/ai-reviews/{duel_id}/{user_id}",
    response_model=AiReviewResponse,
    include_in_schema=False,
)
async def write_ai_review(
    duel_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WriteReviewRequest,
    session: AsyncSession = Depends(get_db),
) -> AiReviewResponse:
    return await AiReviewService(session).write_result(duel_id, user_id, data)


# --- Telegram (бот) ----------------------------------------------------------


@router.post(
    "/telegram/redeem",
    response_model=RedeemResponse,
    include_in_schema=False,
)
async def telegram_redeem(
    data: RedeemRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedeemResponse:
    return await TelegramService(session, redis).redeem(data)


@router.get(
    "/telegram/user/{telegram_user_id}",
    response_model=ResolveResponse,
    include_in_schema=False,
)
async def telegram_resolve(
    telegram_user_id: int,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ResolveResponse:
    return await TelegramService(session, redis).resolve(telegram_user_id)
