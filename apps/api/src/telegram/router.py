"""HTTP-роутер telegram: привязка (auth) + публичный SVG-виджет рейтинга.

Внутренние эндпоинты бота (/internal/telegram/*) — в src/internal_api/router.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from src.auth.dependencies import get_current_user, rate_limit_user
from src.core.db import get_db
from src.core.redis import get_redis
from src.telegram.schemas import LinkCodeResponse
from src.telegram.service import TelegramService
from src.telegram.widget import load_widget_data, render_not_found, render_widget
from src.users.models import User

router = APIRouter(tags=["telegram"])

# Кэш виджета в README — 5 минут (как в спеке).
_WIDGET_CACHE = "public, max-age=300"


@router.post(
    "/me/telegram/link-code",
    response_model=LinkCodeResponse,
    dependencies=[Depends(rate_limit_user("tg_link_code", limit=10, window_s=60))],
)
async def create_link_code(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> LinkCodeResponse:
    """Генерит одноразовый код привязки Telegram (TTL 10 мин в Redis)."""
    return await TelegramService(session, redis).create_link_code(current_user.id)


@router.delete("/me/telegram", status_code=204)
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    """Отвязывает Telegram текущего пользователя."""
    await TelegramService(session, redis).unlink(current_user.id)


@router.get("/widget/{username}.svg", include_in_schema=False)
async def rating_widget(
    username: str = Path(min_length=1, max_length=64),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Публичный SVG-бейдж рейтинга. Несуществующий/забаненный → нейтральный (200)."""
    data = await load_widget_data(session, username)
    svg = render_widget(data) if data is not None else render_not_found()
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": _WIDGET_CACHE},
    )
