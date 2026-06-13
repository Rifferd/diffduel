"""Интеграционные тесты AI-разбора дуэли (Pro-функция).

events.produce замокан (autouse) — CI без брокера остаётся зелёным.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.core import events
from src.core.security import create_access_token, hash_password
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
async def _mock_kafka(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[list[dict[str, object]]]:
    """Перехватывает produce — события в памяти, без брокера."""
    captured: list[dict[str, object]] = []

    async def _fake_produce(
        topic: str, *, key: str, event_type: str, payload: dict[str, object]
    ) -> None:
        captured.append({"topic": topic, "key": key, "type": event_type, "payload": payload})

    monkeypatch.setattr(events, "produce", _fake_produce)
    yield captured


async def _make_user(username: str, *, pro: bool = False) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        uid = await conn.fetchval(
            "INSERT INTO users (email, username, password_hash, email_verified) "
            "VALUES ($1,$2,$3,true) RETURNING id",
            f"{username}@example.com",
            username,
            hash_password("verylongpassword1"),
        )
        if pro:
            await conn.execute(
                "INSERT INTO subscriptions (user_id, plan, status, current_period_end, provider) "
                "VALUES ($1, 'pro', 'active', now() + interval '30 days', 'manual')",
                uid,
            )
        return uuid.UUID(str(uid))
    finally:
        await conn.close()


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def _make_finished_duel(
    client: AsyncClient, a: uuid.UUID, b: uuid.UUID
) -> tuple[uuid.UUID, list[str]]:
    """Создаёт дуэль и завершает её (A выигрывает), возвращает (duel_id, task_ids)."""
    resp = await client.post(
        "/internal/duels",
        json={"topic": "sql", "player_a": str(a), "player_b": str(b)},
        headers=_TOKEN,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    duel_id = uuid.UUID(body["duel_id"])
    tids = [t["id"] for t in body["tasks"]]

    def _ans(correct_flags: list[bool]) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for tid, flag in zip(tids, correct_flags, strict=True):
            out.append(
                {
                    "task_id": tid,
                    "selected": 0 if flag else None,
                    "time_ms": 1000 if flag else None,
                    "correct": flag,
                }
            )
        return out

    finish = await client.post(
        f"/internal/duels/{duel_id}/finish",
        json={
            "finished_at": datetime.now(tz=UTC).isoformat(),
            "results": {
                str(a): {"answers": _ans([True, True, True, False, False])},
                str(b): {"answers": _ans([True, False, False, False, False])},
            },
            "reason": "completed",
        },
        headers=_TOKEN,
    )
    assert finish.status_code == 200, finish.text
    return duel_id, tids


# --- пейволл ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_review_requires_pro(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("air_a")
    b = await _make_user("air_b")
    duel_id, _ = await _make_finished_duel(client, a, b)

    resp = await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "pro_required"


@pytest.mark.asyncio
async def test_request_review_pending_for_pro(
    client: AsyncClient, _mock_kafka: list[dict[str, object]]
) -> None:
    await seed()
    a = await _make_user("airp_a", pro=True)
    b = await _make_user("airp_b")
    duel_id, _ = await _make_finished_duel(client, a, b)

    resp = await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending"
    # Событие ai.review.requested спродюсировано.
    assert any(e["type"] == "ai.review.requested" for e in _mock_kafka)
    evt = next(e for e in _mock_kafka if e["type"] == "ai.review.requested")
    assert evt["payload"] == {"duel_id": str(duel_id), "user_id": str(a)}


@pytest.mark.asyncio
async def test_request_review_idempotent(
    client: AsyncClient, _mock_kafka: list[dict[str, object]]
) -> None:
    await seed()
    a = await _make_user("airi_a", pro=True)
    b = await _make_user("airi_b")
    duel_id, _ = await _make_finished_duel(client, a, b)

    first = await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    second = await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "pending"
    # Повтор не плодит событий: ровно одно ai.review.requested.
    assert sum(e["type"] == "ai.review.requested" for e in _mock_kafka) == 1


@pytest.mark.asyncio
async def test_request_review_non_participant_403(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("airn_a", pro=True)
    b = await _make_user("airn_b")
    outsider = await _make_user("airn_out", pro=True)
    duel_id, _ = await _make_finished_duel(client, a, b)

    resp = await client.post(f"/ai/review/{duel_id}", headers=_headers(outsider))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "not_participant"


@pytest.mark.asyncio
async def test_request_review_not_finished(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("airf_a", pro=True)
    b = await _make_user("airf_b")
    # Дуэль создана, но НЕ завершена.
    resp = await client.post(
        "/internal/duels",
        json={"topic": "sql", "player_a": str(a), "player_b": str(b)},
        headers=_TOKEN,
    )
    duel_id = resp.json()["duel_id"]
    review = await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    assert review.status_code == 422
    assert review.json()["error"]["code"] == "not_finished"


# --- GET --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_review_after_request(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("airg_a", pro=True)
    b = await _make_user("airg_b")
    duel_id, _ = await _make_finished_duel(client, a, b)

    await client.post(f"/ai/review/{duel_id}", headers=_headers(a))
    resp = await client.get(f"/ai/review/{duel_id}", headers=_headers(a))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_get_review_not_requested_404(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("airq_a", pro=True)
    b = await _make_user("airq_b")
    duel_id, _ = await _make_finished_duel(client, a, b)

    resp = await client.get(f"/ai/review/{duel_id}", headers=_headers(a))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ai_review_not_found"


# --- internal: review-data + запись результата ------------------------------


@pytest.mark.asyncio
async def test_internal_review_data(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("aird_a", pro=True)
    b = await _make_user("aird_b")
    duel_id, tids = await _make_finished_duel(client, a, b)

    resp = await client.get(f"/internal/duels/{duel_id}/review-data?user_id={a}", headers=_TOKEN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["topic"] == "sql"
    assert len(body["tasks"]) == 5
    # Эталон присутствует только в internal-ответе.
    for task in body["tasks"]:
        assert "answer" in task
        assert task["task_id"] in tids
    # Первые 3 ответа A верные.
    correct_count = sum(1 for t in body["tasks"] if t["is_correct"])
    assert correct_count == 3


@pytest.mark.asyncio
async def test_internal_review_data_requires_token(client: AsyncClient) -> None:
    resp = await client.get(f"/internal/duels/{uuid.uuid4()}/review-data?user_id={uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_internal_write_result_idempotent(client: AsyncClient) -> None:
    await seed()
    a = await _make_user("airw_a", pro=True)
    b = await _make_user("airw_b")
    duel_id, _ = await _make_finished_duel(client, a, b)
    await client.post(f"/ai/review/{duel_id}", headers=_headers(a))

    write = await client.post(
        f"/internal/ai-reviews/{duel_id}/{a}",
        json={"status": "done", "content": "Разбор: подтяни JOIN-ы."},
        headers=_TOKEN,
    )
    assert write.status_code == 200, write.text
    assert write.json()["status"] == "done"

    # Игрок видит готовый разбор.
    got = await client.get(f"/ai/review/{duel_id}", headers=_headers(a))
    assert got.json()["status"] == "done"
    assert got.json()["content"] == "Разбор: подтяни JOIN-ы."

    # Повторная запись (failed) перезаписывает идемпотентно.
    again = await client.post(
        f"/internal/ai-reviews/{duel_id}/{a}",
        json={"status": "failed", "error": "AI-разбор временно недоступен"},
        headers=_TOKEN,
    )
    assert again.status_code == 200
    assert again.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_internal_write_requires_token(client: AsyncClient) -> None:
    resp = await client.post(
        f"/internal/ai-reviews/{uuid.uuid4()}/{uuid.uuid4()}",
        json={"status": "done", "content": "x"},
    )
    assert resp.status_code == 401
