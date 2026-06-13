"""Интеграционные тесты Pro-подписки: grant/revoke, is_pro в /me и профиле,
RBAC на admin-эндпоинтах, пейволл 402/200 на расширенной статистике."""

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


# --- grant / revoke + is_pro в /me ------------------------------------------


@pytest.mark.asyncio
async def test_grant_pro_sets_is_pro_in_me(client: AsyncClient) -> None:
    admin = await _make_user("padmin", role="admin")
    target = await _make_user("protarget")

    # До выдачи — не Pro.
    me = await client.get("/me", headers=_headers(target))
    assert me.status_code == 200
    assert me.json()["is_pro"] is False

    grant = await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 30}
    )
    assert grant.status_code == 200, grant.text
    assert grant.json()["is_pro"] is True
    assert grant.json()["current_period_end"] is not None

    me2 = await client.get("/me", headers=_headers(target))
    assert me2.json()["is_pro"] is True


@pytest.mark.asyncio
async def test_revoke_pro_clears_is_pro(client: AsyncClient) -> None:
    admin = await _make_user("padmin2", role="admin")
    target = await _make_user("protarget2")

    await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 30}
    )
    assert (await client.get("/me", headers=_headers(target))).json()["is_pro"] is True

    revoke = await client.post(f"/admin/users/{target}/revoke-pro", headers=_headers(admin))
    assert revoke.status_code == 200
    assert revoke.json()["is_pro"] is False

    assert (await client.get("/me", headers=_headers(target))).json()["is_pro"] is False
    # Идемпотентно: повторный revoke не падает.
    assert (
        await client.post(f"/admin/users/{target}/revoke-pro", headers=_headers(admin))
    ).status_code == 200


@pytest.mark.asyncio
async def test_grant_pro_extends_existing(client: AsyncClient) -> None:
    admin = await _make_user("padmin3", role="admin")
    target = await _make_user("protarget3")

    g1 = await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 10}
    )
    end1 = g1.json()["current_period_end"]
    g2 = await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 10}
    )
    end2 = g2.json()["current_period_end"]
    # Продление от предыдущего срока — конец сдвигается вперёд.
    assert end2 > end1


@pytest.mark.asyncio
async def test_is_pro_in_public_profile(client: AsyncClient) -> None:
    admin = await _make_user("padmin4", role="admin")
    target = await _make_user("publicpro")

    prof = await client.get("/users/publicpro")
    assert prof.status_code == 200
    assert prof.json()["is_pro"] is False

    await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 30}
    )
    prof2 = await client.get("/users/publicpro")
    assert prof2.json()["is_pro"] is True


# --- RBAC --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_pro_rbac(client: AsyncClient) -> None:
    user = await _make_user("plain", role="user")
    mod = await _make_user("modx", role="moderator")
    target = await _make_user("victimpro")

    # user → 403, moderator → 403 (только admin).
    r_user = await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(user), json={"days": 5}
    )
    assert r_user.status_code == 403
    r_mod = await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(mod), json={"days": 5}
    )
    assert r_mod.status_code == 403
    # без auth → 401.
    assert (
        await client.post(f"/admin/users/{target}/grant-pro", json={"days": 5})
    ).status_code == 401


# --- Пейволл /me/stats -------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_paywall_for_non_pro(client: AsyncClient) -> None:
    user = await _make_user("nopro")
    resp = await client.get("/me/stats", headers=_headers(user))
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "pro_required"


@pytest.mark.asyncio
async def test_stats_ok_for_pro(client: AsyncClient) -> None:
    await seed()
    admin = await _make_user("padmin5", role="admin")
    target = await _make_user("statspro")
    await client.post(
        f"/admin/users/{target}/grant-pro", headers=_headers(admin), json={"days": 30}
    )

    # Решим пару задач, чтобы статистика была непустой.
    tasks = await client.get("/tasks/training?topic=sql&limit=2", headers=_headers(target))
    for t in tasks.json():
        await client.post(
            "/answers",
            headers=_headers(target),
            json={"task_id": t["id"], "answer": {"selected": 0}, "time_ms": 1500},
        )

    resp = await client.get("/me/stats?period=30", headers=_headers(target))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["period_days"] == 30
    assert body["total_answered"] >= 1
    assert isinstance(body["topics"], list)
