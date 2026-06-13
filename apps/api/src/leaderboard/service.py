"""Бизнес-логика лидербордов: чтение топа/позиции, обновление ZSET, регидратация.

Решения сверх спеки (задокументированы в ADR-0001/комментариях):
- lb:global.score = max Эло среди тем игрока (ZADD ... GT, score только растёт
  в рамках обновления одного игрока — простое и осмысленное для MVP).
- Регидратация ленивая: если нужный ZSET пуст, перестраиваем его из ratings (PG)
  один раз перед чтением. Идемпотентно (replace = DEL+ZADD в pipeline).
- weekly-лидерборд накапливает за ISO-неделю; при регидратации пустого weekly
  наполняем текущими Эло (исторических снимков по неделям не храним — MVP).
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.avatars import avatar_url
from src.leaderboard import keys
from src.leaderboard.repository import (
    LeaderboardPgRepository,
    LeaderboardRedisRepository,
    RankedMember,
)
from src.leaderboard.schemas import LeaderboardEntry, MyLeaderboardPosition

# Соседи для GET /leaderboard/me: ±2 вокруг моей позиции.
_NEIGHBORS = 2


class LeaderboardService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis
        self._zset = LeaderboardRedisRepository(redis)
        self._pg = LeaderboardPgRepository(session)

    # --- ключ по запросу -----------------------------------------------------

    def _resolve_key(self, scope: str, topic: str | None) -> str:
        if scope == "weekly":
            return keys.weekly_key()
        if topic:
            return keys.topic_key(topic)
        return keys.GLOBAL_KEY

    # --- чтение --------------------------------------------------------------

    async def top(self, *, scope: str, topic: str | None, limit: int) -> list[LeaderboardEntry]:
        key = self._resolve_key(scope, topic)
        await self._ensure_populated(key, scope=scope, topic=topic)
        ranked = await self._zset.top(key, limit)
        return await self._enrich(ranked)

    async def my_position(
        self, *, user_id: uuid.UUID, scope: str, topic: str | None
    ) -> MyLeaderboardPosition:
        key = self._resolve_key(scope, topic)
        await self._ensure_populated(key, scope=scope, topic=topic)
        rank0 = await self._zset.rank_of(key, user_id)
        if rank0 is None:
            return MyLeaderboardPosition(rank=None, entries=[])
        ranked = await self._zset.range_with_scores(key, rank0 - _NEIGHBORS, rank0 + _NEIGHBORS)
        return MyLeaderboardPosition(rank=rank0 + 1, entries=await self._enrich(ranked))

    async def _enrich(self, ranked: list[RankedMember]) -> list[LeaderboardEntry]:
        """Батч-обогащение карточками (один WHERE id = ANY). Забаненных скрываем."""
        cards = await self._pg.user_cards([m.user_id for m in ranked])
        out: list[LeaderboardEntry] = []
        for m in ranked:
            card = cards.get(m.user_id)
            if card is None:
                continue  # забанен/удалён — не светим в публичном топе
            out.append(
                LeaderboardEntry(
                    rank=m.rank,
                    user_id=m.user_id,
                    username=card.username,
                    avatar_url=avatar_url(card.avatar_key),
                    elo=m.elo,
                )
            )
        return out

    # --- ленивая регидратация ------------------------------------------------

    async def _ensure_populated(self, key: str, *, scope: str, topic: str | None) -> None:
        """Если ZSET пуст — перестроить из PG один раз."""
        if await self._zset.card_count(key) > 0:
            return
        if scope == "weekly":
            await self._rehydrate_weekly(key)
        elif topic:
            await self._rehydrate_topic(key, topic)
        else:
            await self._rehydrate_global(key)

    async def _rehydrate_topic(self, key: str, slug: str) -> None:
        rows = await self._pg.ratings_by_topic(slug)
        await self._zset.replace(key, {str(uid): float(elo) for uid, elo in rows})

    async def _rehydrate_global(self, key: str) -> None:
        rows = await self._pg.max_elo_per_user()
        await self._zset.replace(key, {str(uid): float(elo) for uid, elo in rows})

    async def _rehydrate_weekly(self, key: str) -> None:
        """Пустой weekly наполняем max Эло по игрокам (снимков по неделям нет — MVP)."""
        rows = await self._pg.max_elo_per_user()
        await self._zset.replace(key, {str(uid): float(elo) for uid, elo in rows})


async def update_on_finish(
    redis: Redis,
    *,
    topic_slug: str,
    new_elo: dict[uuid.UUID, int],
) -> None:
    """Обновляет ZSET-лидерборды после finish-транзакции (вне транзакции БД).

    Вызывается рядом с produce ``duels.finished`` (после commit). Best-effort:
    падение Redis не должно ронять finish-ответ — ловим на стороне вызывающего.
    """
    zset = LeaderboardRedisRepository(redis)
    topic_k = keys.topic_key(topic_slug)
    weekly_k = keys.weekly_key()
    for user_id, elo in new_elo.items():
        await zset.update_member(topic_k, user_id, elo)
        await zset.update_member(weekly_k, user_id, elo)
        # global = max Эло среди тем игрока → растёт только вверх.
        await zset.update_member_max(keys.GLOBAL_KEY, user_id, elo)
