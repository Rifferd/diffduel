"""HTTP-роутер topics: GET /topics (только активные, отсортированные)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.topics.repository import TopicRepository
from src.topics.schemas import TopicPublic

router = APIRouter(tags=["topics"])


@router.get("/topics", response_model=list[TopicPublic])
async def list_topics(session: AsyncSession = Depends(get_db)) -> list[TopicPublic]:
    topics = await TopicRepository(session).list_active()
    return [TopicPublic.model_validate(topic) for topic in topics]
