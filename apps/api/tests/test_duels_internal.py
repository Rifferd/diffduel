"""Интеграционные тесты дуэльных internal-эндпоинтов.

events.produce замокан (autouse) — CI без брокера остаётся зелёным.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.core import events
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


async def _rating(user_id: uuid.UUID, topic_slug: str = "sql") -> dict[str, int] | None:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchrow(
            """
            SELECT r.elo, r.games, r.wins, r.streak
            FROM ratings r JOIN topics t ON t.id = r.topic_id
            WHERE r.user_id = $1 AND t.slug = $2
            """,
            user_id,
            topic_slug,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def _duel_row(duel_id: uuid.UUID) -> dict[str, object] | None:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchrow("SELECT * FROM duels WHERE id = $1", duel_id)
        return dict(row) if row else None
    finally:
        await conn.close()


async def _count_duel_answers(duel_id: uuid.UUID) -> int:
    conn = await asyncpg.connect(**_DB)
    try:
        return await conn.fetchval("SELECT count(*) FROM answers WHERE duel_id = $1", duel_id)
    finally:
        await conn.close()


_Created = tuple[uuid.UUID, uuid.UUID, uuid.UUID, dict[str, object]]
CreateFn = Callable[[str, str], Awaitable[_Created]]


@pytest_asyncio.fixture
async def make_duel(client: AsyncClient) -> CreateFn:
    async def _create(a_suffix: str, b_suffix: str) -> _Created:
        await seed()
        a = await _make_user(a_suffix)
        b = await _make_user(b_suffix)
        resp = await client.post(
            "/internal/duels",
            json={"topic": "sql", "player_a": str(a), "player_b": str(b)},
            headers=_TOKEN,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        return uuid.UUID(body["duel_id"]), a, b, body

    return _create


def _answers(
    task_ids: list[str], *correct_flags: bool, time_ms: int = 1000
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for task_id, flag in zip(task_ids, correct_flags, strict=False):
        out.append(
            {
                "task_id": task_id,
                "selected": 0 if flag else None,
                "time_ms": time_ms if flag else None,
                "correct": flag,
            }
        )
    return out


def _task_ids(body: dict[str, object]) -> list[str]:
    tasks = body["tasks"]
    assert isinstance(tasks, list)
    return [t["id"] for t in tasks]


# --- create ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_duel(make_duel: CreateFn) -> None:
    duel_id, a, b, body = await make_duel("ca", "cb")
    # 5 задач, эталоны присутствуют (internal-ответ).
    assert len(body["tasks"]) == 5
    for task in body["tasks"]:
        assert "answer" in task
        assert task["time_limit_s"] == 30
    # Рейтинги обоих игроков — базовые 1200.
    assert body["ratings"][str(a)] == 1200
    assert body["ratings"][str(b)] == 1200
    # duels-строка создана в статусе running.
    row = await _duel_row(duel_id)
    assert row is not None
    assert row["status"] == "running"
    assert row["started_at"] is not None
    # Строки ratings заведены заранее.
    assert await _rating(a) is not None
    assert await _rating(b) is not None


@pytest.mark.asyncio
async def test_create_duel_unknown_topic(client: AsyncClient) -> None:
    a, b = await _make_user("ua"), await _make_user("ub")
    resp = await client.post(
        "/internal/duels",
        json={"topic": "no-such", "player_a": str(a), "player_b": str(b)},
        headers=_TOKEN,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "topic_not_found"


@pytest.mark.asyncio
async def test_create_requires_token(client: AsyncClient) -> None:
    a, b = await _make_user("na"), await _make_user("nb")
    resp = await client.post(
        "/internal/duels",
        json={"topic": "sql", "player_a": str(a), "player_b": str(b)},
    )
    assert resp.status_code == 401


# --- finish ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_happy_path(
    client: AsyncClient, make_duel: CreateFn, _mock_kafka: list[dict[str, object]]
) -> None:
    duel_id, a, b, created = await make_duel("ha", "hb")
    tids = _task_ids(created)
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True, True, True, False, False)},
            str(b): {"answers": _answers(tids, True, False, False, False, False)},
        },
        "reason": "completed",
    }
    resp = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # A победил (3 против 1).
    assert body["winner_id"] == str(a)
    assert body["deltas"][str(a)] == 16
    assert body["deltas"][str(b)] == -16
    assert body["elo"][str(a)] == 1216
    assert body["elo"][str(b)] == 1184

    # БД: ratings обновлены, duels.finished, deltas сохранены.
    ra, rb = await _rating(a), await _rating(b)
    assert ra is not None and rb is not None
    assert ra["elo"] == 1216 and ra["wins"] == 1 and ra["games"] == 1 and ra["streak"] == 1
    assert rb["elo"] == 1184 and rb["wins"] == 0 and rb["games"] == 1 and rb["streak"] == 0
    row = await _duel_row(duel_id)
    assert row is not None
    assert row["status"] == "finished"
    assert row["winner_id"] == a
    assert row["rating_delta_a"] == 16
    assert row["rating_delta_b"] == -16
    assert row["finished_at"] is not None
    # 10 ответов (по 5 на игрока) с duel_id.
    assert await _count_duel_answers(duel_id) == 10
    # Событие duels.finished продюсировано.
    assert any(e["type"] == "duels.finished" for e in _mock_kafka)


@pytest.mark.asyncio
async def test_finish_draw(client: AsyncClient, make_duel: CreateFn) -> None:
    duel_id, a, b, created = await make_duel("da", "db")
    tids = _task_ids(created)
    # Равный счёт и равное время → ничья.
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True, True, False, False, False, time_ms=1000)},
            str(b): {"answers": _answers(tids, True, True, False, False, False, time_ms=1000)},
        },
        "reason": "completed",
    }
    resp = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    body = resp.json()
    assert body["winner_id"] is None
    assert body["deltas"][str(a)] == 0
    assert body["deltas"][str(b)] == 0
    row = await _duel_row(duel_id)
    assert row is not None and row["status"] == "finished" and row["winner_id"] is None


@pytest.mark.asyncio
async def test_finish_tiebreak_by_time(client: AsyncClient, make_duel: CreateFn) -> None:
    duel_id, a, b, created = await make_duel("ta", "tb")
    tids = _task_ids(created)
    # Равный счёт, но A быстрее по верным → A победил.
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True, True, False, False, False, time_ms=500)},
            str(b): {"answers": _answers(tids, True, True, False, False, False, time_ms=2000)},
        },
        "reason": "completed",
    }
    resp = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    body = resp.json()
    assert body["winner_id"] == str(a)
    assert body["deltas"][str(a)] == 16


@pytest.mark.asyncio
async def test_finish_idempotent(client: AsyncClient, make_duel: CreateFn) -> None:
    duel_id, a, b, created = await make_duel("ia", "ib")
    tids = _task_ids(created)
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True, True, True, False, False)},
            str(b): {"answers": _answers(tids, False, False, False, False, False)},
        },
        "reason": "completed",
    }
    first = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    assert first.status_code == 200
    second = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    assert second.status_code == 200
    # Повтор возвращает те же deltas и НЕ двоит начисление.
    assert first.json()["deltas"] == second.json()["deltas"]
    assert first.json()["winner_id"] == second.json()["winner_id"]
    ra = await _rating(a)
    assert ra is not None
    assert ra["games"] == 1  # начислено ровно один раз
    assert await _count_duel_answers(duel_id) == 10  # ответы записаны один раз


@pytest.mark.asyncio
async def test_finish_aborted(client: AsyncClient, make_duel: CreateFn) -> None:
    duel_id, a, b, created = await make_duel("aa", "ab")
    tids = _task_ids(created)
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, False, False, False, False, False)},
            str(b): {"answers": _answers(tids, False, False, False, False, False)},
        },
        "reason": "aborted",
    }
    resp = await client.post(f"/internal/duels/{duel_id}/finish", json=payload, headers=_TOKEN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["winner_id"] is None
    assert body["deltas"] == {}
    # Эло не тронут, ответы не записаны, статус aborted.
    ra = await _rating(a)
    assert ra is not None and ra["elo"] == 1200 and ra["games"] == 0
    row = await _duel_row(duel_id)
    assert row is not None and row["status"] == "aborted"
    assert await _count_duel_answers(duel_id) == 0


@pytest.mark.asyncio
async def test_finish_unknown_duel(client: AsyncClient) -> None:
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(uuid.uuid4()): {"answers": _answers([str(uuid.uuid4())], True)},
            str(uuid.uuid4()): {"answers": _answers([str(uuid.uuid4())], True)},
        },
        "reason": "completed",
    }
    resp = await client.post(f"/internal/duels/{uuid.uuid4()}/finish", json=payload, headers=_TOKEN)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "duel_not_found"


@pytest.mark.asyncio
async def test_finish_requires_token(client: AsyncClient, make_duel: CreateFn) -> None:
    duel_id, a, b, created = await make_duel("za", "zb")
    tids = _task_ids(created)
    payload = {
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "results": {
            str(a): {"answers": _answers(tids, True)},
            str(b): {"answers": _answers(tids, True)},
        },
        "reason": "completed",
    }
    resp = await client.post(f"/internal/duels/{duel_id}/finish", json=payload)
    assert resp.status_code == 401
