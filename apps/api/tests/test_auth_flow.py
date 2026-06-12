"""Интеграционные тесты полного auth-флоу."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.auth.cookies import REFRESH_COOKIE_NAME

_REG = {
    "email": "alice@example.com",
    "username": "alice_01",
    "password": "verylongpassword1",
}


async def _register(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json=_REG)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient) -> None:
    await _register(client)

    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    assert login.status_code == 200, login.text
    body = login.json()
    access = body["access_token"]
    assert body["token_type"] == "bearer"
    # refresh — в httpOnly cookie на path=/auth.
    assert REFRESH_COOKIE_NAME in login.cookies

    me = await client.get("/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice_01"
    assert me.json()["email"] == _REG["email"]


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] in {"unauthorized", "invalid_token"}


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client: AsyncClient) -> None:
    await _register(client)
    dup = await client.post(
        "/auth/register",
        json={"email": _REG["email"], "username": "other_user", "password": "verylongpassword1"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "email_taken"


@pytest.mark.asyncio
async def test_login_wrong_password_is_generic(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": "wrongwrongwrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"
    # Тот же код для несуществующего пользователя.
    resp2 = await client.post(
        "/auth/login", json={"email": "nope@example.com", "password": "whatever123"}
    )
    assert resp2.status_code == 401
    assert resp2.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_short_password_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": "b@example.com", "username": "bob_99", "password": "short"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_invalid_username_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": "c@example.com", "username": "ab", "password": "verylongpassword1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(client: AsyncClient) -> None:
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    old_refresh = login.cookies[REFRESH_COOKIE_NAME]

    # Первый refresh: ротация, новый токен.
    r1 = await client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: old_refresh})
    assert r1.status_code == 200, r1.text
    new_refresh = r1.cookies[REFRESH_COOKIE_NAME]
    assert new_refresh != old_refresh
    assert r1.json()["access_token"]

    # Повторный refresh СТАРЫМ токеном → reuse detection → 401 + отзыв family.
    reuse = await client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "invalid_refresh_token"

    # Новый токен тоже мёртв (вся family отозвана).
    dead = await client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: new_refresh})
    assert dead.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_family(client: AsyncClient) -> None:
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    refresh = login.cookies[REFRESH_COOKIE_NAME]

    out = await client.post("/auth/logout", cookies={REFRESH_COOKIE_NAME: refresh})
    assert out.status_code == 204

    after = await client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: refresh})
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_update_me_username(client: AsyncClient) -> None:
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    patch = await client.patch("/me", json={"username": "alice_new"}, headers=headers)
    assert patch.status_code == 200
    assert patch.json()["username"] == "alice_new"


@pytest.mark.asyncio
async def test_register_rate_limit(client: AsyncClient) -> None:
    # Лимит 5/мин/IP на /auth/register.
    statuses = []
    for i in range(7):
        resp = await client.post(
            "/auth/register",
            json={
                "email": f"rl{i}@example.com",
                "username": f"rluser{i}",
                "password": "verylongpassword1",
            },
        )
        statuses.append(resp.status_code)
    assert 429 in statuses
    # Последний 429 имеет Retry-After.
    last = await client.post(
        "/auth/register",
        json={"email": "rl9@example.com", "username": "rluser9", "password": "verylongpassword1"},
    )
    assert last.status_code == 429
    assert "retry-after" in {k.lower() for k in last.headers}


@pytest.mark.asyncio
async def test_rotation_claim_is_atomic() -> None:
    """Победитель claim_for_rotation ровно один — второй claim тем же токеном = reuse."""
    import uuid
    from datetime import UTC, datetime, timedelta

    from src.auth.repository import RefreshTokenRepository
    from src.core.db import get_sessionmaker
    from src.core.security import hash_password, hash_refresh_token
    from src.users.repository import UserRepository

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = await UserRepository(session).create(
            email=f"atomic-{uuid.uuid4().hex[:8]}@example.com",
            username=f"atomic{uuid.uuid4().hex[:8]}",
            password_hash=hash_password("verylongpassword1"),
        )
        repo = RefreshTokenRepository(session)
        now = datetime.now(tz=UTC)
        token = await repo.create(
            user_id=user.id,
            token_hash=hash_refresh_token("raw-token-atomicity-test"),
            expires_at=now + timedelta(days=30),
        )
        await session.commit()

        assert await repo.claim_for_rotation(token.id, now=now) is True
        await session.commit()
        # Повторный claim того же токена обязан проиграть.
        assert await repo.claim_for_rotation(token.id, now=now) is False
        await session.commit()
