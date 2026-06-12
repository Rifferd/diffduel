"""Async Redis-клиент (один на процесс) + FastAPI-зависимость."""

from __future__ import annotations

from redis.asyncio import Redis

from src.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Ленивая инициализация async Redis-клиента."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    """Закрывает соединение при остановке приложения."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
