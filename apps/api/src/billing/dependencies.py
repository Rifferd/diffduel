"""FastAPI-зависимости billing: пейволл require_pro (402 pro_required)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.billing.service import is_pro
from src.core.db import get_db
from src.core.errors import PaymentRequiredError
from src.users.models import User


async def require_pro(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Пейволл: 402 ``pro_required`` без активной Pro-подписки.

    401 (нет/битый токен, бан) отдаётся раньше — это решает get_current_user.
    """
    if not await is_pro(session, current_user):
        raise PaymentRequiredError("Требуется Pro-подписка", code="pro_required")
    return current_user
