"""HTTP-роутер дневного челленджа (auth, НЕ Pro-гейтед).

- GET  /daily             — задача дня (ленивый выбор, без эталона)
- POST /daily/answer      — зачётный ответ (один в день; rate limit)
- GET  /daily/leaderboard — топ-N дня с никами (без N+1)
- GET  /daily/me          — моя позиция дня
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, rate_limit_user
from src.core.db import get_db
from src.core.redis import get_redis
from src.daily.schemas import (
    DailyAnswerResult,
    DailyAnswerSubmit,
    DailyLeaderboardEntry,
    DailyMyPosition,
    DailyTask,
)
from src.daily.service import DailyService
from src.users.models import User

router = APIRouter(tags=["daily"])


@router.get("/daily", response_model=DailyTask)
async def get_daily(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DailyTask:
    return await DailyService(session, redis).task_of_day()


@router.post(
    "/daily/answer",
    response_model=DailyAnswerResult,
    dependencies=[Depends(rate_limit_user("daily_answer", limit=30, window_s=60))],
)
async def answer_daily(
    data: DailyAnswerSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DailyAnswerResult:
    return await DailyService(session, redis).submit(user_id=current_user.id, data=data)


@router.get("/daily/leaderboard", response_model=list[DailyLeaderboardEntry])
async def daily_leaderboard(
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[DailyLeaderboardEntry]:
    return await DailyService(session, redis).leaderboard(limit=limit)


@router.get("/daily/me", response_model=DailyMyPosition)
async def daily_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DailyMyPosition:
    return await DailyService(session, redis).my_position(user_id=current_user.id)
