"""Идемпотентная регидратация всех ZSET-лидербордов из ratings (PG).

Запуск: ``uv run python -m src.leaderboard_rebuild`` (по DATABASE_URL/REDIS_URL
из окружения). Наполняет lb:topic:{slug} по активным темам, lb:global и
текущий lb:weekly значениями max Эло. Повторный прогон даёт тот же результат
(replace = DEL+ZADD в pipeline).
"""

from __future__ import annotations

import asyncio

from src.core.db import dispose_engine, get_sessionmaker
from src.core.logging import configure_logging, get_logger
from src.core.redis import close_redis, get_redis
from src.leaderboard import keys
from src.leaderboard.repository import LeaderboardPgRepository, LeaderboardRedisRepository

logger = get_logger("leaderboard_rebuild")


async def rebuild() -> dict[str, int]:
    """Перестраивает все лидерборды. Возвращает {key: число членов}."""
    redis = get_redis()
    zset = LeaderboardRedisRepository(redis)
    sessionmaker = get_sessionmaker()
    counts: dict[str, int] = {}

    async with sessionmaker() as session:
        pg = LeaderboardPgRepository(session)

        # Per-topic.
        for slug in await pg.active_topic_slugs():
            rows = await pg.ratings_by_topic(slug)
            members = {str(uid): float(elo) for uid, elo in rows}
            key = keys.topic_key(slug)
            await zset.replace(key, members)
            counts[key] = len(members)

        # Global + текущая неделя — по max Эло игрока.
        max_rows = await pg.max_elo_per_user()
        members = {str(uid): float(elo) for uid, elo in max_rows}
        await zset.replace(keys.GLOBAL_KEY, members)
        counts[keys.GLOBAL_KEY] = len(members)
        weekly = keys.weekly_key()
        await zset.replace(weekly, members)
        counts[weekly] = len(members)

    logger.info("leaderboard_rebuilt", keys=len(counts))
    return counts


async def _main() -> None:
    configure_logging()
    counts = await rebuild()
    logger.info("leaderboard_rebuild_done", **{k: v for k, v in counts.items()})
    await close_redis()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())
