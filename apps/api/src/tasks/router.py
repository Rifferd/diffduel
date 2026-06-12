"""HTTP-роутер tasks: GET /tasks/training, POST /answers (соло-режим)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, rate_limit_user
from src.core.db import get_db
from src.tasks.schemas import AnswerResult, AnswerSubmit, TaskPublic
from src.tasks.service import TaskService
from src.users.models import User

router = APIRouter(tags=["tasks"])


@router.get("/tasks/training", response_model=list[TaskPublic])
async def training(
    topic: str = Query(min_length=1, max_length=64),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TaskPublic]:
    tasks = await TaskService(session).training(
        topic_slug=topic, difficulty=difficulty, limit=limit
    )
    return [TaskPublic.model_validate(task) for task in tasks]


@router.post(
    "/answers",
    response_model=AnswerResult,
    dependencies=[Depends(rate_limit_user("answers_submit", limit=60, window_s=60))],
)
async def submit_answer(
    data: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AnswerResult:
    return await TaskService(session).submit_answer(user_id=current_user.id, data=data)
