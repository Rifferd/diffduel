"""Кэш фиче-флагов в Redis (TTL 30с) с инвалидацией при изменении.

get_flag — публичный хелпер для остального кода: читает из кэша, при промахе
подтягивает из PG и кэширует. invalidate — вызывается из админки при PUT.
"""

from __future__ import annotations

import json

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.models import FeatureFlag

_TTL_S = 30
_MISS = "__miss__"


def _cache_key(key: str) -> str:
    return f"ff:{key}"


async def get_flag(session: AsyncSession, redis: Redis, key: str) -> dict[str, object] | None:
    """Возвращает {enabled, payload} флага (или None, если флага нет).

    Кэш Redis TTL 30с; отрицательный результат тоже кэшируется (анти-стампида).
    """
    cached = await redis.get(_cache_key(key))
    if cached is not None:
        if cached == _MISS:
            return None
        parsed: dict[str, object] = json.loads(cached)
        return parsed

    stmt = select(FeatureFlag).where(FeatureFlag.key == key)
    flag = (await session.execute(stmt)).scalar_one_or_none()
    if flag is None:
        await redis.set(_cache_key(key), _MISS, ex=_TTL_S)
        return None

    value: dict[str, object] = {"enabled": flag.enabled, "payload": flag.payload}
    await redis.set(_cache_key(key), json.dumps(value, default=str), ex=_TTL_S)
    return value


async def invalidate(redis: Redis, key: str) -> None:
    """Сбрасывает кэш флага (после PUT)."""
    await redis.delete(_cache_key(key))
