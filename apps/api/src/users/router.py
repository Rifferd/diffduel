"""HTTP-роутер users: GET /me, PATCH /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, rate_limit_user
from src.core.db import get_db
from src.users.models import User
from src.users.schemas import (
    AvatarConfirmRequest,
    AvatarPresignRequest,
    AvatarPresignResponse,
    UserMe,
    UserProfile,
    UserUpdate,
)
from src.users.service import UserService

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserMe)
async def get_me(current_user: User = Depends(get_current_user)) -> UserMe:
    return UserMe.model_validate(current_user)


@router.patch("/me", response_model=UserMe)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    user = await UserService(session).update_me(current_user, data)
    return UserMe.model_validate(user)


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
