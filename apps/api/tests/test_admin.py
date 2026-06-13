"""Интеграционные тесты админки: RBAC, пайплайн публикации, бан/разбан
(+ что забаненный не логинится), фиче-флаги CRUD и кэш-инвалидация."""

from __future__ import annotations

import uuid

import asyncpg
import pytest
from httpx import AsyncClient

from src.admin import flags_cache
from src.core.redis import get_redis
from src.core.security import create_access_token
from src.seeds import seed

_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


async def _make_user(
    username: str, *, role: str = "user", password: str | None = None
) -> uuid.UUID:
    from src.core.security import hash_password

    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO users (email, username, role, password_hash, email_verified) "
            "VALUES ($1,$2,$3,$4,true) RETURNING id",
            f"{username}@example.com",
            username,
            role,
            hash_password(password) if password else None,
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


# --- RBAC --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_user_forbidden(client: AsyncClient) -> None:
    u = await _make_user("plainuser", role="user")
    resp = await client.get("/admin/tasks", headers=_headers(u))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_rbac_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/admin/tasks")).status_code == 401


@pytest.mark.asyncio
async def test_rbac_moderator_tasks_ok_users_forbidden(client: AsyncClient) -> None:
    mod = await _make_user("mod1", role="moderator")
    assert (await client.get("/admin/tasks", headers=_headers(mod))).status_code == 200
    # users — только admin.
    resp = await client.get("/admin/users", headers=_headers(mod))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rbac_admin_all_access(client: AsyncClient) -> None:
    admin = await _make_user("admin1", role="admin")
    assert (await client.get("/admin/tasks", headers=_headers(admin))).status_code == 200
    assert (await client.get("/admin/users", headers=_headers(admin))).status_code == 200
    assert (await client.get("/admin/metrics/overview", headers=_headers(admin))).status_code == 200


# --- Пайплайн публикации -----------------------------------------------------


@pytest.mark.asyncio
async def test_task_publish_pipeline(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("admin2", role="admin")
    tid = await _topic_id("sql")
    create = await client.post(
        "/admin/tasks",
        headers=_headers(admin),
        json={
            "topic_id": str(tid),
            "difficulty": 2,
            "type": "quiz",
            "body": {"question": "2+2?", "options": ["3", "4"]},
            "answer": {"correct": 1},
        },
    )
    assert create.status_code == 201, create.text
    task = create.json()
    assert task["status"] == "draft"
    task_id = task["id"]

    # publish: draft → published.
    pub = await client.post(f"/admin/tasks/{task_id}/publish", headers=_headers(admin))
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"

    # повторная публикация — конфликт.
    again = await client.post(f"/admin/tasks/{task_id}/publish", headers=_headers(admin))
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_task_publish_validates_quiz(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("admin3", role="admin")
    tid = await _topic_id("sql")
    # correct вне диапазона опций → 422 уже на создании.
    resp = await client.post(
        "/admin/tasks",
        headers=_headers(admin),
        json={
            "topic_id": str(tid),
            "difficulty": 1,
            "type": "quiz",
            "body": {"question": "?", "options": ["a", "b"]},
            "answer": {"correct": 5},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_task_answer"


@pytest.mark.asyncio
async def test_task_reject_returns_to_draft(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("admin4", role="admin")
    tid = await _topic_id("sql")
    created = await client.post(
        "/admin/tasks",
        headers=_headers(admin),
        json={
            "topic_id": str(tid),
            "difficulty": 1,
            "type": "quiz",
            "body": {"question": "?", "options": ["a", "b"]},
            "answer": {"correct": 0},
        },
    )
    task_id = created.json()["id"]
    rej = await client.post(f"/admin/tasks/{task_id}/reject", headers=_headers(admin))
    assert rej.status_code == 200
    assert rej.json()["status"] == "draft"


# --- Бан / разбан ------------------------------------------------------------


@pytest.mark.asyncio
async def test_ban_unban_and_banned_cannot_login(client: AsyncClient) -> None:
    admin = await _make_user("admin5", role="admin")
    victim = await _make_user("victim", role="user", password="verylongpassword1")

    # До бана логин работает.
    login_ok = await client.post(
        "/auth/login", json={"email": "victim@example.com", "password": "verylongpassword1"}
    )
    assert login_ok.status_code == 200

    ban = await client.post(
        f"/admin/users/{victim}/ban", headers=_headers(admin), json={"reason": "спам"}
    )
    assert ban.status_code == 200
    assert ban.json()["banned_at"] is not None

    # Забаненный больше не логинится.
    login_banned = await client.post(
        "/auth/login", json={"email": "victim@example.com", "password": "verylongpassword1"}
    )
    assert login_banned.status_code == 401
    assert login_banned.json()["error"]["code"] == "account_banned"

    # Разбан возвращает доступ.
    unban = await client.post(f"/admin/users/{victim}/unban", headers=_headers(admin))
    assert unban.status_code == 200
    assert unban.json()["banned_at"] is None
    login_again = await client.post(
        "/auth/login", json={"email": "victim@example.com", "password": "verylongpassword1"}
    )
    assert login_again.status_code == 200


@pytest.mark.asyncio
async def test_moderator_cannot_ban(client: AsyncClient) -> None:
    mod = await _make_user("mod2", role="moderator")
    victim = await _make_user("victim2", role="user")
    resp = await client.post(
        f"/admin/users/{victim}/ban", headers=_headers(mod), json={"reason": "x"}
    )
    assert resp.status_code == 403


# --- Feature flags -----------------------------------------------------------


@pytest.mark.asyncio
async def test_feature_flag_crud_and_cache(client: AsyncClient) -> None:
    admin = await _make_user("admin6", role="admin")
    redis = get_redis()

    # Создание через PUT.
    put = await client.put(
        "/admin/feature-flags/new_arena",
        headers=_headers(admin),
        json={"enabled": True, "payload": {"max": 10}},
    )
    assert put.status_code == 200, put.text
    assert put.json()["enabled"] is True
    assert put.json()["payload"] == {"max": 10}

    # Кэш: get_flag читает из PG и кэширует.
    from src.core.db import get_sessionmaker

    async with get_sessionmaker()() as session:
        flag = await flags_cache.get_flag(session, redis, "new_arena")
        assert flag == {"enabled": True, "payload": {"max": 10}}
    assert await redis.get("ff:new_arena") is not None

    # PUT инвалидирует кэш — ключ удалён.
    upd = await client.put(
        "/admin/feature-flags/new_arena",
        headers=_headers(admin),
        json={"enabled": False, "payload": None},
    )
    assert upd.status_code == 200
    assert await redis.get("ff:new_arena") is None

    # Следующее чтение видит свежее значение.
    async with get_sessionmaker()() as session:
        flag = await flags_cache.get_flag(session, redis, "new_arena")
        assert flag == {"enabled": False, "payload": None}

    # list.
    lst = await client.get("/admin/feature-flags", headers=_headers(admin))
    assert lst.status_code == 200
    assert any(f["key"] == "new_arena" for f in lst.json())


@pytest.mark.asyncio
async def test_feature_flag_negative_cache(client: AsyncClient) -> None:
    redis = get_redis()
    from src.core.db import get_sessionmaker

    async with get_sessionmaker()() as session:
        assert await flags_cache.get_flag(session, redis, "missing") is None
    # Отрицательный результат закэширован.
    assert await redis.get("ff:missing") == "__miss__"
