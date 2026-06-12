"""Тесты Lua sliding-window rate-limit на реальном Redis."""

from __future__ import annotations

import pytest

from src.core.errors import RateLimitedError
from src.core.rate_limit import check_rate_limit
from src.core.redis import get_redis


@pytest.mark.asyncio
async def test_sliding_window_allows_up_to_limit() -> None:
    redis = get_redis()
    await redis.flushdb()
    for _ in range(3):
        await check_rate_limit(redis, name="t", identity="ip1", limit=3, window_s=60)


@pytest.mark.asyncio
async def test_sliding_window_blocks_over_limit() -> None:
    redis = get_redis()
    await redis.flushdb()
    for _ in range(3):
        await check_rate_limit(redis, name="t2", identity="ip", limit=3, window_s=60)
    with pytest.raises(RateLimitedError) as exc:
        await check_rate_limit(redis, name="t2", identity="ip", limit=3, window_s=60)
    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert "Retry-After" in exc.value.headers


@pytest.mark.asyncio
async def test_sliding_window_isolated_per_identity() -> None:
    redis = get_redis()
    await redis.flushdb()
    for _ in range(2):
        await check_rate_limit(redis, name="t3", identity="a", limit=2, window_s=60)
    # Другой identity не затронут.
    await check_rate_limit(redis, name="t3", identity="b", limit=2, window_s=60)
