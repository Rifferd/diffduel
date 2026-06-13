"""Интеграционные тесты дневного челленджа: ленивый выбор задачи (стабильность),
один зачётный ответ в день, дневной лидерборд и позиция."""

from __future__ import annotations

import uuid

import asyncpg
import pytest
from httpx import AsyncClient

from src.core.security import create_access_token, hash_password
from src.seeds import seed

_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


async def _make_user(username: str) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO users (email, username, role, password_hash, email_verified) "
            "VALUES ($1,$2,'user',$3,true) RETURNING id",
            f"{username}@example.com",
            username,
            hash_password("verylongpassword1"),
        )
        return uuid.UUID(str(row))
    finally:
        await conn.close()


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def _correct_selected(client: AsyncClient, user_id: uuid.UUID, task: dict) -> int:
    """Находит верную опцию задачи через соло-проверку (сервер — источник правды)."""
    n = len(task["body"]["options"])
    for idx in range(n):
        sub = await client.post(
            "/answers",
            headers=_headers(user_id),
            json={"task_id": task["id"], "answer": {"selected": idx}, "time_ms": 1500},
        )
        if sub.json()["correct"]:
            return idx
    raise AssertionError("нет верной опции")


@pytest.mark.asyncio
async def test_daily_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/daily")).status_code == 401


@pytest.mark.asyncio
async def test_daily_lazy_pick_is_stable(client: AsyncClient) -> None:
    await seed()
    user = await _make_user("dailyuser")

    first = await client.get("/daily", headers=_headers(user))
    assert first.status_code == 200, first.text
    body = first.json()
    assert "answer" not in first.text and "correct" not in first.text
    task_id = body["task"]["id"]

    # Повторный GET (другой юзер) — та же задача дня.
    other = await _make_user("dailyuser2")
    second = await client.get("/daily", headers=_headers(other))
    assert second.json()["task"]["id"] == task_id
    assert second.json()["challenge_date"] == body["challenge_date"]


@pytest.mark.asyncio
async def test_daily_single_scored_answer(client: AsyncClient) -> None:
    await seed()
    user = await _make_user("dailyplayer")
    daily = (await client.get("/daily", headers=_headers(user))).json()
    task = daily["task"]

    # Первый ответ — зачётный (scored=True).
    first = await client.post(
        "/daily/answer",
        headers=_headers(user),
        json={"answer": {"selected": 0}, "time_ms": 2000},
    )
    assert first.status_code == 200, first.text
    assert first.json()["scored"] is True
    assert first.json()["already_answered"] is False

    # Повторный — результат есть, но в лидерборд не идёт.
    second = await client.post(
        "/daily/answer",
        headers=_headers(user),
        json={"answer": {"selected": 1}, "time_ms": 1000},
    )
    assert second.status_code == 200
    assert second.json()["scored"] is False
    assert second.json()["already_answered"] is True
    # task передан для возможной отладки локально.
    assert task["id"]


@pytest.mark.asyncio
async def test_daily_leaderboard_and_my_position(client: AsyncClient) -> None:
    await seed()
    fast = await _make_user("fastsolver")
    slow = await _make_user("slowsolver")
    wrong = await _make_user("wrongsolver")

    daily = (await client.get("/daily", headers=_headers(fast))).json()
    task = daily["task"]
    correct = await _correct_selected(client, fast, task)

    # fast — верно и быстро; slow — верно, но медленно; wrong — неверно.
    await client.post(
        "/daily/answer",
        headers=_headers(fast),
        json={"answer": {"selected": correct}, "time_ms": 500},
    )
    await client.post(
        "/daily/answer",
        headers=_headers(slow),
        json={"answer": {"selected": correct}, "time_ms": 5000},
    )
    wrong_idx = next(i for i in range(len(task["body"]["options"])) if i != correct)
    await client.post(
        "/daily/answer",
        headers=_headers(wrong),
        json={"answer": {"selected": wrong_idx}, "time_ms": 800},
    )

    lb = await client.get("/daily/leaderboard")
    assert lb.status_code == 200
    rows = lb.json()
    assert len(rows) == 3
    # fast быстрее slow → выше; wrong (score 0) — последний.
    assert rows[0]["user_id"] == str(fast)
    assert rows[1]["user_id"] == str(slow)
    assert rows[2]["user_id"] == str(wrong)
    assert rows[0]["score"] > rows[1]["score"] > rows[2]["score"]
    assert rows[0]["rank"] == 1
    assert all("username" in r for r in rows)

    # Моя позиция.
    me_fast = await client.get("/daily/me", headers=_headers(fast))
    assert me_fast.json()["rank"] == 1
    me_slow = await client.get("/daily/me", headers=_headers(slow))
    assert me_slow.json()["rank"] == 2

    # Не игравший — rank null.
    bystander = await _make_user("bystander")
    me_none = await client.get("/daily/me", headers=_headers(bystander))
    assert me_none.json()["rank"] is None
    assert me_none.json()["score"] is None


@pytest.mark.asyncio
async def test_daily_answer_validation(client: AsyncClient) -> None:
    await seed()
    user = await _make_user("dailyval")
    await client.get("/daily", headers=_headers(user))
    # time_ms вне диапазона → 422.
    bad = await client.post(
        "/daily/answer",
        headers=_headers(user),
        json={"answer": {"selected": 0}, "time_ms": 5},
    )
    assert bad.status_code == 422
