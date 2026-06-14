"""Интеграционные тесты турниров: список/детали, вход (402 заглушка / бесплатно /
повтор), задачи без эталона, ответ и накопление score, один зачётный ответ на
задачу, RBAC admin CRUD + grant-entry, пересчёт мест RANK()."""

from __future__ import annotations

import uuid
from decimal import Decimal

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


async def _make_user(username: str, *, role: str = "user") -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO users (email, username, role, password_hash, email_verified) "
            "VALUES ($1,$2,$3,$4,true) RETURNING id",
            f"{username}@example.com",
            username,
            role,
            hash_password("verylongpassword1"),
        )
        return uuid.UUID(str(row))
    finally:
        await conn.close()


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def _topic_id(slug: str = "sql") -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        return uuid.UUID(str(await conn.fetchval("SELECT id FROM topics WHERE slug=$1", slug)))
    finally:
        await conn.close()


async def _create_tournament(
    client: AsyncClient,
    admin: uuid.UUID,
    *,
    entry_fee: str = "0",
    status: str = "active",
    task_count: int = 2,
    topic: str = "sql",
) -> dict:
    tid = await _topic_id(topic)
    resp = await client.post(
        "/admin/tournaments",
        headers=_headers(admin),
        json={
            "title": "Кубок SQL",
            "topic_id": str(tid),
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2027-01-01T00:00:00Z",
            "entry_fee": entry_fee,
            "prize_pool": "100",
            "task_count": task_count,
            "status": status,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _correct_selected(client: AsyncClient, user: uuid.UUID, task: dict) -> int:
    """Находит верную опцию через соло-проверку (сервер — источник правды)."""
    for idx in range(len(task["body"]["options"])):
        sub = await client.post(
            "/answers",
            headers=_headers(user),
            json={"task_id": task["id"], "answer": {"selected": idx}, "time_ms": 1500},
        )
        if sub.json()["correct"]:
            return idx
    raise AssertionError("нет верной опции")


# --- Список / детали ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_and_detail(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin", role="admin")
    created = await _create_tournament(client, admin)

    lst = await client.get("/tournaments")
    assert lst.status_code == 200
    rows = lst.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    assert rows[0]["entries_count"] == 0

    # Фильтр по статусу.
    assert (await client.get("/tournaments?status=upcoming")).json() == []

    detail = await client.get(f"/tournaments/{created['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["tasks_count"] == 2
    assert body["leaderboard"] == []
    # Эталоны не утекают в детали.
    assert "answer" not in detail.text and "correct" not in detail.text


@pytest.mark.asyncio
async def test_detail_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/tournaments/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "tournament_not_found"


# --- Вход (enter) ------------------------------------------------------------


@pytest.mark.asyncio
async def test_enter_free_and_repeat(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin2", role="admin")
    t = await _create_tournament(client, admin, entry_fee="0")
    player = await _make_user("t_player")

    first = await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    assert first.status_code == 200, first.text
    assert first.json()["joined"] is True
    assert first.json()["already_entered"] is False

    # Повторный вход — 200, idемпотентно.
    again = await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    assert again.status_code == 200
    assert again.json()["already_entered"] is True

    detail = await client.get(f"/tournaments/{t['id']}")
    assert detail.json()["entries_count"] == 1


@pytest.mark.asyncio
async def test_enter_paid_is_402_stub(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin3", role="admin")
    t = await _create_tournament(client, admin, entry_fee="500")
    player = await _make_user("t_payer")

    resp = await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "entry_payment_unavailable"


@pytest.mark.asyncio
async def test_enter_requires_auth(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin4", role="admin")
    t = await _create_tournament(client, admin)
    assert (await client.post(f"/tournaments/{t['id']}/enter")).status_code == 401


# --- Задачи без эталона ------------------------------------------------------


@pytest.mark.asyncio
async def test_tasks_without_answer_and_participant_only(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin5", role="admin")
    t = await _create_tournament(client, admin)
    player = await _make_user("t_taskuser")

    # Не участник → 403.
    forbidden = await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "not_participant"

    await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    tasks = await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))
    assert tasks.status_code == 200
    body = tasks.json()
    assert len(body["tasks"]) == 2
    # Эталоны/объяснения не утекают.
    assert "answer" not in tasks.text and "explanation" not in tasks.text


# --- Ответ + накопление score / один зачётный ответ -------------------------


@pytest.mark.asyncio
async def test_answer_accumulates_score_single_scored(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin6", role="admin")
    t = await _create_tournament(client, admin, task_count=2)
    player = await _make_user("t_solver")
    await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))

    tasks = (await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))).json()[
        "tasks"
    ]
    task0, task1 = tasks[0], tasks[1]
    correct0 = await _correct_selected(client, player, task0)

    # Первый ответ на task0 — зачтён.
    r1 = await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(player),
        json={"task_id": task0["id"], "answer": {"selected": correct0}, "time_ms": 1000},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["scored"] is True
    assert r1.json()["correct"] is True
    score_after_first = r1.json()["score"]
    assert score_after_first > 0
    assert r1.json()["finished"] is False  # ещё одна задача не отвечена

    # Повторный ответ на ту же задачу — не зачитывается, score не растёт.
    r2 = await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(player),
        json={"task_id": task0["id"], "answer": {"selected": correct0}, "time_ms": 100},
    )
    assert r2.status_code == 200
    assert r2.json()["scored"] is False
    assert r2.json()["already_answered"] is True
    assert r2.json()["score"] == score_after_first

    # Ответ на вторую задачу закрывает entry (finished=True).
    correct1 = await _correct_selected(client, player, task1)
    r3 = await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(player),
        json={"task_id": task1["id"], "answer": {"selected": correct1}, "time_ms": 2000},
    )
    assert r3.status_code == 200
    assert r3.json()["scored"] is True
    assert r3.json()["finished"] is True
    assert r3.json()["score"] > score_after_first


@pytest.mark.asyncio
async def test_answer_requires_active_and_membership(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin7", role="admin")
    t = await _create_tournament(client, admin, status="upcoming")
    player = await _make_user("t_early")

    # upcoming → задачи недоступны (даже без членства: статус проверяется).
    resp = await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "tournament_not_active"


# --- Пересчёт мест RANK() ----------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_places_rank(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin8", role="admin")
    t = await _create_tournament(client, admin, task_count=1)

    fast = await _make_user("rank_fast")
    slow = await _make_user("rank_slow")
    wrong = await _make_user("rank_wrong")
    for u in (fast, slow, wrong):
        await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(u))

    task = (await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(fast))).json()[
        "tasks"
    ][0]
    correct = await _correct_selected(client, fast, task)
    wrong_idx = next(i for i in range(len(task["body"]["options"])) if i != correct)

    await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(fast),
        json={"task_id": task["id"], "answer": {"selected": correct}, "time_ms": 500},
    )
    await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(slow),
        json={"task_id": task["id"], "answer": {"selected": correct}, "time_ms": 5000},
    )
    await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(wrong),
        json={"task_id": task["id"], "answer": {"selected": wrong_idx}, "time_ms": 800},
    )

    # До пересчёта места не проставлены.
    before = await client.get(f"/tournaments/{t['id']}")
    assert all(row["place"] is None for row in before.json()["leaderboard"])

    rec = await client.post(
        f"/admin/tournaments/{t['id']}/recompute-places", headers=_headers(admin)
    )
    assert rec.status_code == 204

    detail = await client.get(f"/tournaments/{t['id']}")
    lb = detail.json()["leaderboard"]
    assert len(lb) == 3
    # fast быстрее slow → 1 и 2; wrong (score 0) — последний.
    by_user = {row["user_id"]: row for row in lb}
    assert by_user[str(fast)]["place"] == 1
    assert by_user[str(slow)]["place"] == 2
    assert by_user[str(wrong)]["place"] == 3
    # Лидерборд отсортирован: первым — fast.
    assert lb[0]["user_id"] == str(fast)


@pytest.mark.asyncio
async def test_finish_status_auto_recomputes_places(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin9", role="admin")
    t = await _create_tournament(client, admin, task_count=1)
    player = await _make_user("finisher")
    await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    task = (await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))).json()[
        "tasks"
    ][0]
    correct = await _correct_selected(client, player, task)
    await client.post(
        f"/tournaments/{t['id']}/answer",
        headers=_headers(player),
        json={"task_id": task["id"], "answer": {"selected": correct}, "time_ms": 700},
    )

    # PATCH status=finished → авто-пересчёт мест.
    patch = await client.patch(
        f"/admin/tournaments/{t['id']}",
        headers=_headers(admin),
        json={"status": "finished"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "finished"

    detail = await client.get(f"/tournaments/{t['id']}")
    assert detail.json()["leaderboard"][0]["place"] == 1


# --- RBAC admin CRUD + grant-entry ------------------------------------------


@pytest.mark.asyncio
async def test_admin_rbac(client: AsyncClient) -> None:
    await seed()
    tid = await _topic_id("sql")
    plain = await _make_user("t_plain", role="user")
    payload = {
        "title": "X",
        "topic_id": str(tid),
        "starts_at": "2026-01-01T00:00:00Z",
        "task_count": 1,
    }
    # Обычный юзер → 403, без токена → 401.
    assert (
        await client.post("/admin/tournaments", headers=_headers(plain), json=payload)
    ).status_code == 403
    assert (await client.post("/admin/tournaments", json=payload)).status_code == 401

    # moderator — может создавать (как задачи).
    mod = await _make_user("t_mod", role="moderator")
    ok = await client.post("/admin/tournaments", headers=_headers(mod), json=payload)
    assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_admin_create_validates_task_set(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin10", role="admin")
    tid = await _topic_id("sql")
    # Ни task_ids, ни task_count → 422.
    resp = await client.post(
        "/admin/tournaments",
        headers=_headers(admin),
        json={"title": "X", "topic_id": str(tid), "starts_at": "2026-01-01T00:00:00Z"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "task_set_required"

    # Слишком много задач → not_enough_tasks.
    resp2 = await client.post(
        "/admin/tournaments",
        headers=_headers(admin),
        json={
            "title": "X",
            "topic_id": str(tid),
            "starts_at": "2026-01-01T00:00:00Z",
            "task_count": 9999,
        },
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_admin_grant_entry(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin11", role="admin")
    t = await _create_tournament(client, admin, entry_fee="500")  # платный
    player = await _make_user("granted")

    # Платный вход напрямую недоступен.
    assert (
        await client.post(f"/tournaments/{t['id']}/enter", headers=_headers(player))
    ).status_code == 402

    # Админ выдаёт вход вручную.
    grant = await client.post(
        f"/admin/tournaments/{t['id']}/grant-entry",
        headers=_headers(admin),
        json={"user_id": str(player)},
    )
    assert grant.status_code == 200, grant.text
    assert grant.json()["joined"] is True

    # Теперь участник видит задачи.
    tasks = await client.get(f"/tournaments/{t['id']}/tasks", headers=_headers(player))
    assert tasks.status_code == 200

    # Повторный grant — idемпотентно.
    again = await client.post(
        f"/admin/tournaments/{t['id']}/grant-entry",
        headers=_headers(admin),
        json={"user_id": str(player)},
    )
    assert again.json()["already_entered"] is True


@pytest.mark.asyncio
async def test_admin_update_and_explicit_task_ids(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("t_admin12", role="admin")
    tid = await _topic_id("sql")
    # Берём явные published task_ids темы.
    conn = await asyncpg.connect(**_DB)
    try:
        rows = await conn.fetch(
            "SELECT id FROM tasks WHERE topic_id=$1 AND status='published' LIMIT 2", tid
        )
    finally:
        await conn.close()
    explicit = [str(r["id"]) for r in rows]

    created = await client.post(
        "/admin/tournaments",
        headers=_headers(admin),
        json={
            "title": "Explicit",
            "topic_id": str(tid),
            "starts_at": "2026-01-01T00:00:00Z",
            "task_ids": explicit,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["task_ids"] == explicit

    # PATCH title.
    upd = await client.patch(
        f"/admin/tournaments/{created.json()['id']}",
        headers=_headers(admin),
        json={"title": "Renamed", "prize_pool": "777"},
    )
    assert upd.status_code == 200
    assert upd.json()["title"] == "Renamed"
    assert Decimal(upd.json()["prize_pool"]) == Decimal("777")
