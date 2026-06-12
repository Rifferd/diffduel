"""HTTP-роутер users: GET /me, PATCH /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.core.db import get_db
from src.users.models import User
from src.users.schemas import UserMe, UserUpdate
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
