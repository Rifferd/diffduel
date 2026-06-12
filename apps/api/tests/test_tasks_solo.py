"""Интеграционные тесты соло-режима: тренировки, проверка ответов, сид."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.seeds import seed


async def _auth_headers(client: AsyncClient, *, suffix: str = "solo") -> dict[str, str]:
    reg = {
        "email": f"{suffix}@example.com",
        "username": f"user_{suffix}",
        "password": "verylongpassword1",
    }
    resp = await client.post("/auth/register", json=reg)
    assert resp.status_code == 201, resp.text
    login = await client.post(
        "/auth/login", json={"email": reg["email"], "password": reg["password"]}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_seed_is_idempotent() -> None:
    assert await seed() == 150
    assert await seed() == 150


@pytest.mark.asyncio
async def test_training_never_leaks_answer(client: AsyncClient) -> None:
    await seed()
    headers = await _auth_headers(client, suffix="noleak")

    resp = await client.get("/tasks/training?topic=python&limit=20", headers=headers)
    assert resp.status_code == 200, resp.text
    tasks = resp.json()
    assert 1 <= len(tasks) <= 20
    # Ни эталона, ни объяснения нет нигде в сыром ответе.
    raw = resp.text
    assert '"answer"' not in raw
    assert '"correct"' not in raw
    assert '"explanation"' not in raw
    for task in tasks:
        assert set(task) == {"id", "type", "difficulty", "body"}


@pytest.mark.asyncio
async def test_training_requires_auth_and_validates(client: AsyncClient) -> None:
    assert (await client.get("/tasks/training?topic=python")).status_code == 401
    headers = await _auth_headers(client, suffix="val")
    missing = await client.get("/tasks/training?topic=no-such-topic", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "topic_not_found"
    bad_limit = await client.get("/tasks/training?topic=python&limit=100", headers=headers)
    assert bad_limit.status_code == 422


@pytest.mark.asyncio
async def test_submit_answer_flow(client: AsyncClient) -> None:
    await seed()
    headers = await _auth_headers(client, suffix="answers")

    resp = await client.get("/tasks/training?topic=sql&limit=1", headers=headers)
    task = resp.json()[0]
    n_options = len(task["body"]["options"])

    # Перебором найдём верный ответ (сервер - единственный источник правды).
    verdicts = []
    for idx in range(n_options):
        sub = await client.post(
            "/answers",
            json={"task_id": task["id"], "answer": {"selected": idx}, "time_ms": 1500},
            headers=headers,
        )
        assert sub.status_code == 200, sub.text
        body = sub.json()
        assert body["correct_option"] in range(n_options)
        assert body["explanation"]
        verdicts.append(body["correct"])
    assert verdicts.count(True) == 1

    # После верного ответа already_solved становится True.
    again = await client.post(
        "/answers",
        json={"task_id": task["id"], "answer": {"selected": 0}, "time_ms": 1500},
        headers=headers,
    )
    assert again.json()["already_solved"] is True


@pytest.mark.asyncio
async def test_submit_answer_validation(client: AsyncClient) -> None:
    await seed()
    headers = await _auth_headers(client, suffix="badsub")

    not_found = await client.post(
        "/answers",
        json={
            "task_id": "00000000-0000-0000-0000-000000000000",
            "answer": {"selected": 0},
            "time_ms": 1500,
        },
        headers=headers,
    )
    assert not_found.status_code == 404

    resp = await client.get("/tasks/training?topic=javascript&limit=1", headers=headers)
    task_id = resp.json()[0]["id"]
    for bad in (
        {"task_id": task_id, "answer": {"selected": -1}, "time_ms": 1500},
        {"task_id": task_id, "answer": {"selected": 0}, "time_ms": 5},
        {"task_id": task_id, "answer": {}, "time_ms": 1500},
    ):
        assert (await client.post("/answers", json=bad, headers=headers)).status_code == 422
