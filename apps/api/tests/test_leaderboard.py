"""Интеграционные тесты лидербордов: ZADD при finish, топ-N, моя позиция,
ленивая регидратация из пустого ZSET."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.core import events
from src.core.redis import get_redis
from src.leaderboard import keys
from src.seeds import seed

_TOKEN = {"X-Internal-Token": "test-internal-token"}
_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


@pytest_asyncio.fixture(autouse=True)
async def _mock_kafka(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    async def _fake(topic: str, *, key: str, event_type: str, payload: dict[str, object]) -> None:
        return None

    monkeypatch.setattr(events, "produce", _fake)
    yield


async def _make_user(suffix: str) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO users (email, username) VALUES ($1, $2) RETURNING id",
            f"{suffix}@example.com",
            f"user_{suffix}",
        )
        return uuid.UUID(str(row))
    finally:
        await conn.close()


async def _topic_id(slug: str = "sql") -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        return uuid.UUID(str(await conn.fetchval("SELECT id FROM topics WHERE slug=$1", slug)))
    finally:
        await conn.close()


async def _set_rating(user_id: uuid.UUID, topic_id: uuid.UUID, elo: int) -> None:
    conn = await asyncpg.connect(**_DB)
    try:
        await conn.execute(
            """
            INSERT INTO ratings (user_id, topic_id, elo) VALUES ($1,$2,$3)
            ON CONFLICT (user_id, topic_id) DO UPDATE SET elo = EXCLUDED.elo
            """,
            user_id,
            topic_id,
            elo,
        )
    finally:
        await conn.close()


def _answers(task_ids: list[str], *flags: bool) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for tid, flag in zip(task_ids, flags, strict=False):
        out.append(
            {
                "task_id": tid,
                "selected": 0 if flag else None,
                "time_ms": 1000 if flag else None,
                "correct": flag,
            }
        )
    return out


async def _finish_duel(client: AsyncClient, a_suffix: str, b_suffix: str) -> tuple[uuid.UUID, ...]:
    """Создаёт и завершает дуэль (A выигрывает 3:1). Возвращает (a, b)."""
    await seed()
    a, b = await _make_user(a_suffix), await _make_user(b_suffix)
    created = (
        await client.post(
            "/internal/duels",
            json={"topic": "sql", "player_a": str(a), "player_b": str(b)},
            headers=_TOKEN,
        )
    ).json()
    tids = [t["id"] for t in created["tasks"]]
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True, True, True, False, False)},
            str(b): {"answers": _answers(tids, True, False, False, False, False)},
        },
        "reason": "completed",
    }
    resp = await client.post(
        f"/internal/duels/{created['duel_id']}/finish", json=payload, headers=_TOKEN
    )
    assert resp.status_code == 200, resp.text
    return a, b


@pytest.mark.asyncio
async def test_finish_updates_zset(client: AsyncClient) -> None:
    a, b = await _finish_duel(client, "lba", "lbb")
    redis = get_redis()
    # topic / weekly / global ZSET содержат обоих игроков с их новым Эло.
    topic_score = await redis.zscore(keys.topic_key("sql"), str(a))
    assert int(topic_score) == 1216  # победитель +16
    assert int(await redis.zscore(keys.weekly_key(), str(b))) == 1184
    assert int(await redis.zscore(keys.GLOBAL_KEY, str(a))) == 1216


@pytest.mark.asyncio
async def test_top_n_ordered(client: AsyncClient) -> None:
    a, b = await _finish_duel(client, "topa", "topb")
    resp = await client.get("/leaderboard?scope=global&limit=10")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [r["user_id"] for r in rows][:2] == [str(a), str(b)]
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 2
    assert rows[0]["elo"] == 1216
    # Публичный ответ не несёт чувствительных полей.
    assert set(rows[0]) == {"rank", "user_id", "username", "avatar_url", "elo"}


@pytest.mark.asyncio
async def test_my_position_with_neighbors(client: AsyncClient) -> None:
    await seed()
    tid = await _topic_id("sql")
    # 7 игроков с убывающим Эло; цель — 4-й (rank 4).
    users = []
    for i in range(7):
        u = await _make_user(f"pos{i}")
        await _set_rating(u, tid, 1300 - i * 10)
        users.append(u)
    target = users[3]
    from src.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token(target)}"}
    resp = await client.get("/leaderboard/me?scope=global", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rank"] == 4
    # Соседи ±2 → ранги 2..6.
    assert [e["rank"] for e in body["entries"]] == [2, 3, 4, 5, 6]
    assert any(e["user_id"] == str(target) for e in body["entries"])


@pytest.mark.asyncio
async def test_me_absent_returns_null_rank(client: AsyncClient) -> None:
    await seed()
    u = await _make_user("absent")
    from src.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token(u)}"}
    resp = await client.get("/leaderboard/me?scope=global", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["rank"] is None
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_lazy_rehydration_from_empty(client: AsyncClient) -> None:
    """ZSET пуст (Redis потерян) → топ перестраивается из ratings один раз."""
    await seed()
    tid = await _topic_id("sql")
    u1, u2 = await _make_user("rh1"), await _make_user("rh2")
    await _set_rating(u1, tid, 1500)
    await _set_rating(u2, tid, 1400)
    redis = get_redis()
    await redis.flushdb()  # имитируем потерю Redis
    assert await redis.zcard(keys.topic_key("sql")) == 0

    resp = await client.get("/leaderboard?scope=global&topic=sql&limit=10")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [r["user_id"] for r in rows] == [str(u1), str(u2)]
    # После регидратации ZSET наполнен.
    assert await redis.zcard(keys.topic_key("sql")) == 2
