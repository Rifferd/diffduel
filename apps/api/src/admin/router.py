"""HTTP-роутер админки (/admin, RBAC поверх get_current_user).

- moderator + admin: задачи, метрики, фиче-флаги.
- только admin: пользователи и баны.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.schemas import (
    AdminTask,
    AdminTaskList,
    AdminUser,
    AdminUserList,
    BanRequest,
    FeatureFlagOut,
    FeatureFlagUpsert,
    MetricsOverview,
    TaskCreate,
    TaskUpdate,
)
from src.admin.service import AdminService
from src.auth.dependencies import require_role
from src.core.db import get_db
from src.core.enums import TaskStatus, UserRole
from src.core.redis import get_redis
from src.users.models import User

# Весь роутер доступен только moderator/admin; users/* доуточняют до admin.
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.moderator, UserRole.admin))],
)

_admin_only = require_role(UserRole.admin)


# --- Tasks (moderator + admin) ----------------------------------------------


@router.get("/tasks", response_model=AdminTaskList)
async def list_tasks(
    status: TaskStatus | None = Query(default=None),
    topic: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTaskList:
    return await AdminService(session, redis).list_tasks(
        status=status, topic_id=topic, page=page, page_size=page_size
    )


@router.post("/tasks", response_model=AdminTask, status_code=201)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(require_role(UserRole.moderator, UserRole.admin)),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTask:
    return await AdminService(session, redis).create_task(data, author_id=current_user.id)


@router.patch("/tasks/{task_id}", response_model=AdminTask)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTask:
    return await AdminService(session, redis).update_task(task_id, data)


@router.post("/tasks/{task_id}/publish", response_model=AdminTask)
async def publish_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTask:
    return await AdminService(session, redis).publish_task(task_id)


@router.post("/tasks/{task_id}/reject", response_model=AdminTask)
async def reject_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminTask:
    return await AdminService(session, redis).reject_task(task_id)


# --- Users (admin only) ------------------------------------------------------


@router.get("/users", response_model=AdminUserList, dependencies=[Depends(_admin_only)])
async def list_users(
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminUserList:
    return await AdminService(session, redis).list_users(q=q, page=page, page_size=page_size)


@router.post("/users/{user_id}/ban", response_model=AdminUser, dependencies=[Depends(_admin_only)])
async def ban_user(
    user_id: uuid.UUID,
    data: BanRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminUser:
    return await AdminService(session, redis).ban_user(user_id, data)


@router.post(
    "/users/{user_id}/unban", response_model=AdminUser, dependencies=[Depends(_admin_only)]
)
async def unban_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminUser:
    return await AdminService(session, redis).unban_user(user_id)


# --- Metrics (moderator + admin) --------------------------------------------


@router.get("/metrics/overview", response_model=MetricsOverview)
async def metrics_overview(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MetricsOverview:
    return await AdminService(session, redis).metrics_overview()


# --- Feature flags (moderator + admin) --------------------------------------


@router.get("/feature-flags", response_model=list[FeatureFlagOut])
async def list_flags(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[FeatureFlagOut]:
    return await AdminService(session, redis).list_flags()


@router.put("/feature-flags/{key}", response_model=FeatureFlagOut)
async def upsert_flag(
    key: Annotated[str, Path(min_length=1, max_length=120)],
    data: FeatureFlagUpsert,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> FeatureFlagOut:
    return await AdminService(session, redis).upsert_flag(key, data)
