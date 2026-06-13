"""HTTP-роутер лидербордов: GET /leaderboard (публичный), GET /leaderboard/me (auth)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.core.db import get_db
from src.core.redis import get_redis
from src.leaderboard.schemas import LeaderboardEntry, MyLeaderboardPosition
from src.leaderboard.service import LeaderboardService
from src.users.models import User

router = APIRouter(tags=["leaderboard"])

Scope = Literal["global", "weekly"]


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    scope: Scope = Query(default="global"),
    topic: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[LeaderboardEntry]:
    return await LeaderboardService(session, redis).top(scope=scope, topic=topic, limit=limit)


@router.get("/leaderboard/me", response_model=MyLeaderboardPosition)
async def get_my_position(
    scope: Scope = Query(default="global"),
    topic: str | None = Query(default=None, min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MyLeaderboardPosition:
    return await LeaderboardService(session, redis).my_position(
        user_id=current_user.id, scope=scope, topic=topic
    )
