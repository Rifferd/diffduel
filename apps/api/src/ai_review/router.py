"""HTTP-роутер AI-разбора дуэли (Pro-функция).

- POST /ai/review/{duel_id} (auth + require_pro → 402, участник, дуэль finished)
- GET  /ai/review/{duel_id} (auth, участник)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai_review.schemas import AiReviewResponse
from src.ai_review.service import AiReviewService
from src.auth.dependencies import get_current_user
from src.billing.dependencies import require_pro
from src.core.db import get_db
from src.users.models import User

router = APIRouter(prefix="/ai/review", tags=["ai-review"])


@router.post("/{duel_id}", response_model=AiReviewResponse)
async def request_review(
    duel_id: uuid.UUID,
    current_user: User = Depends(require_pro),
    session: AsyncSession = Depends(get_db),
) -> AiReviewResponse:
    return await AiReviewService(session).request(duel_id, current_user.id)


@router.get("/{duel_id}", response_model=AiReviewResponse)
async def get_review(
    duel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AiReviewResponse:
    return await AiReviewService(session).get(duel_id, current_user.id)
