"""Sliding-window rate limiting на Redis через атомарный Lua-скрипт.

Fail-open для auth запрещён: при недоступном Redis отдаём 503 и логируем.
"""

from __future__ import annotations

import math
import time
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import get_settings
from src.core.errors import RateLimitedError, ServiceUnavailableError
from src.core.logging import get_logger
from src.core.redis import get_redis

logger = get_logger("rate_limit")

# Атомарный sliding-window:
#   KEYS[1] = ключ окна
#   ARGV[1] = now_ms, ARGV[2] = window_ms, ARGV[3] = limit, ARGV[4] = unique member
# Возвращает {allowed(0|1), retry_after_ms}.
_LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, window)
    return {1, 0}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry = window
if oldest[2] then
    retry = (tonumber(oldest[2]) + window) - now
    if retry < 0 then retry = 0 end
end
return {0, retry}
"""

KeyKind = Literal["ip", "user"]


def _client_ip(request: Request) -> str:
    """IP клиента.

    X-Forwarded-For учитывается только при TRUST_PROXY=true (за нашим Traefik),
    и берётся ПОСЛЕДНИЙ элемент — его дописывает сам прокси, подделать его
    клиент не может. Первый элемент клиент контролирует — брать его нельзя,
    иначе rate limit обходится одним заголовком.
    """
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.rsplit(",", 1)[-1].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


async def check_rate_limit(
    redis: Redis,
    *,
    name: str,
    identity: str,
    limit: int,
    window_s: int,
) -> None:
    """Проверяет лимит. Бросает RateLimitedError / ServiceUnavailableError."""
    now_ms = int(time.time() * 1000)
    window_ms = window_s * 1000
    member = f"{now_ms}-{time.perf_counter_ns()}"
    redis_key = f"rl:{name}:{identity}"
    try:
        result = await redis.eval(
            _LUA_SLIDING_WINDOW,
            1,
            redis_key,
            str(now_ms),
            str(window_ms),
            str(limit),
            member,
        )
    except RedisError:
        # Fail-open запрещён для auth: блокируем запрос и логируем.
        logger.error("rate_limit_redis_unavailable", limiter=name)
        raise ServiceUnavailableError(
            "Сервис временно недоступен, попробуйте позже",
            code="service_unavailable",
        ) from None

    allowed, retry_after_ms = int(result[0]), int(result[1])
    if not allowed:
        retry_after_s = max(1, math.ceil(retry_after_ms / 1000))
        raise RateLimitedError(
            "Слишком много запросов, попробуйте позже",
            details={"retry_after": retry_after_s},
            headers={"Retry-After": str(retry_after_s)},
        )


def rate_limit(
    name: str,
    limit: int,
    window_s: int,
    *,
    key: KeyKind = "ip",
) -> Callable[..., Awaitable[None]]:
    """Фабрика FastAPI-зависимости rate-limit.

    key="ip" — лимит по IP; key="user" — по id текущего пользователя.
    """

    async def _dependency(
        request: Request,
        redis: Redis = Depends(get_redis),
    ) -> None:
        if key == "user":
            user = getattr(request.state, "user", None)
            identity = str(getattr(user, "id", None)) if user else _client_ip(request)
        else:
            identity = _client_ip(request)
        await check_rate_limit(
            redis,
            name=name,
            identity=identity,
            limit=limit,
            window_s=window_s,
        )

    return _dependency
