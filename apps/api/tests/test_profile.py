"""Интеграционные тесты публичного профиля GET /users/{username}:
агрегаты (дуэли/победы/винрейт/streak), Эло по темам, 404 для banned/несуществующего."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


async def _make_user(username: str, *, banned: bool = False) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO users (email, username, banned_at) VALUES ($1,$2,$3) RETURNING id",
            f"{username}@example.com",
            username,
            datetime.now(tz=UTC) if banned else None,
        )
        return uuid.UUID(str(row))
    finally:
        await conn.close()


async def _topic(slug: str, title: str) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        return uuid.UUID(
            str(
                await conn.fetchval(
                    "INSERT INTO topics (slug,title,is_active) VALUES ($1,$2,true) RETURNING id",
                    slug,
                    title,
                )
            )
        )
    finally:
        await conn.close()


async def _rating(user_id: uuid.UUID, topic_id: uuid.UUID, elo: int) -> None:
    conn = await asyncpg.connect(**_DB)
    try:
        await conn.execute(
            "INSERT INTO ratings (user_id, topic_id, elo) VALUES ($1,$2,$3)",
            user_id,
            topic_id,
            elo,
        )
    finally:
        await conn.close()


async def _duel(
    topic_id: uuid.UUID,
    a: uuid.UUID,
    b: uuid.UUID,
    winner: uuid.UUID | None,
    finished_at: datetime,
) -> None:
    conn = await asyncpg.connect(**_DB)
    try:
        await conn.execute(
            """
            INSERT INTO duels (topic_id, status, player_a, player_b, winner_id, finished_at)
            VALUES ($1,'finished',$2,$3,$4,$5)
            """,
            topic_id,
            a,
            b,
            winner,
            finished_at,
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_profile_aggregates(client: AsyncClient) -> None:
    tid = await _topic("sql", "SQL")
    me = await _make_user("alice")
    opp = await _make_user("bob")
    await _rating(me, tid, 1320)

    now = datetime.now(tz=UTC)
    # 5 завершённых дуэлей: исход с конца времени — W, W, L, W, W
    # текущий streak (с самого свежего) = 2 (последние две — победы).
    schedule = [
        (now - timedelta(minutes=1), me),  # самый свежий: win
        (now - timedelta(minutes=2), me),  # win
        (now - timedelta(minutes=3), opp),  # loss (сброс серии)
        (now - timedelta(minutes=4), me),  # win
        (now - timedelta(minutes=5), opp),  # loss
    ]
    for finished_at, winner in schedule:
        # чередуем сторону игрока, чтобы покрыть player_a и player_b
        await _duel(tid, me, opp, winner, finished_at)

    resp = await client.get("/users/alice")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == "alice"
    assert body["total_duels"] == 5
    assert body["wins"] == 3
    assert body["win_rate"] == 0.6
    assert body["streak"] == 2
    assert body["topics"] == [{"slug": "sql", "title": "SQL", "elo": 1320}]
    # Чувствительных полей нет.
    assert "email" not in body and "id" not in body


@pytest.mark.asyncio
async def test_profile_player_b_side_counts(client: AsyncClient) -> None:
    tid = await _topic("py", "Python")
    me = await _make_user("carol")
    opp = await _make_user("dave")
    now = datetime.now(tz=UTC)
    # me как player_b, и побеждает.
    await _duel(tid, opp, me, me, now)
    resp = await client.get("/users/carol")
    body = resp.json()
    assert body["total_duels"] == 1 and body["wins"] == 1 and body["streak"] == 1


@pytest.mark.asyncio
async def test_profile_no_duels(client: AsyncClient) -> None:
    await _make_user("emptyuser")
    resp = await client.get("/users/emptyuser")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_duels"] == 0 and body["wins"] == 0
    assert body["win_rate"] == 0.0 and body["streak"] == 0
    assert body["topics"] == []


@pytest.mark.asyncio
async def test_profile_banned_404(client: AsyncClient) -> None:
    await _make_user("banneduser", banned=True)
    resp = await client.get("/users/banneduser")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "user_not_found"


@pytest.mark.asyncio
async def test_profile_missing_404(client: AsyncClient) -> None:
    resp = await client.get("/users/ghost")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "user_not_found"
