"""HTTP-роутер users: GET /me, PATCH /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, rate_limit_user
from src.billing.dependencies import require_pro
from src.billing.service import is_pro
from src.core.db import get_db
from src.users.models import User
from src.users.schemas import (
    AvatarConfirmRequest,
    AvatarPresignRequest,
    AvatarPresignResponse,
    UserMe,
    UserProfile,
    UserStats,
    UserUpdate,
)
from src.users.service import UserService

router = APIRouter(tags=["users"])


async def _me_payload(session: AsyncSession, user: User) -> UserMe:
    me = UserMe.model_validate(user)
    me.is_pro = await is_pro(session, user)
    return me


@router.get("/me", response_model=UserMe)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    return await _me_payload(session, current_user)


@router.patch("/me", response_model=UserMe)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    user = await UserService(session).update_me(current_user, data)
    return await _me_payload(session, user)


@router.get("/me/stats", response_model=UserStats)
async def my_stats(
    period: int = Query(default=30, ge=1, le=365, description="Период в днях"),
    current_user: User = Depends(require_pro),
    session: AsyncSession = Depends(get_db),
) -> UserStats:
    """Расширенная статистика точности по темам (Pro-функция, иначе 402).

    Решение по не-Pro: пейволл 402 pro_required — урезанную версию не отдаём,
    т.к. это явная Pro-ценность (release2.md §A).
    """
    return await UserService(session).extended_stats(current_user, period_days=period)


@router.post(
    "/me/avatar/presign",
    response_model=AvatarPresignResponse,
    dependencies=[Depends(rate_limit_user("avatar_presign", limit=10, window_s=60))],
)
async def presign_avatar(
    data: AvatarPresignRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AvatarPresignResponse:
    return await UserService(session).presign_avatar(current_user, data)


@router.post("/me/avatar/confirm", response_model=UserMe)
async def confirm_avatar(
    data: AvatarConfirmRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    user = await UserService(session).confirm_avatar(current_user, data.key)
    return UserMe.model_validate(user)


@router.get("/users/{username}", response_model=UserProfile)
async def public_profile(
    username: str,
    session: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Публичный профиль (SEO). Забаненный/несуществующий → 404."""
    return await UserService(session).public_profile(username)
