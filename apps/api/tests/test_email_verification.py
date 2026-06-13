"""Интеграционные тесты подтверждения email (console-бэкенд, без реального SMTP)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.auth.cookies import REFRESH_COOKIE_NAME, VERIFY_SID_COOKIE_NAME
from src.core.config import get_settings
from src.core.security import sha256_hex

_REG = {
    "email": "verify@example.com",
    "username": "verify_user",
    "password": "verylongpassword1",
}

_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


@pytest.fixture
def verification_on() -> Iterator[None]:
    """Включает режим ON через подмену кэшированного синглтона настроек."""
    settings = get_settings()
    original = settings.email_verification_enabled
    object.__setattr__(settings, "email_verification_enabled", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "email_verification_enabled", original)


async def _captured_codes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Перехватывает send_verification_email, копит отправленные код/ссылку."""
    sent: list[dict[str, str]] = []

    async def _fake_send(to: str, code: str, link_url: str) -> None:
        sent.append({"to": to, "code": code, "link_url": link_url})

    monkeypatch.setattr("src.auth.service.send_verification_email", _fake_send)
    return sent


async def _fetch_verification(user_email: str) -> asyncpg.Record | None:
    conn = await asyncpg.connect(**_DB)
    try:
        return await conn.fetchrow(
            "SELECT ev.* FROM email_verifications ev "
            "JOIN users u ON u.id = ev.user_id WHERE u.email = $1",
            user_email,
        )
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def _db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(**_DB)
    try:
        yield conn
    finally:
        await conn.close()


# --- Режим OFF ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_off_returns_tokens(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json=_REG)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["verification_required"] is False
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert REFRESH_COOKIE_NAME in resp.cookies


# --- Режим ON: регистрация ---------------------------------------------------


@pytest.mark.asyncio
async def test_register_on_requires_verification(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    resp = await client.post("/auth/register", json=_REG)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["verification_required"] is True
    assert body.get("access_token") is None
    assert REFRESH_COOKIE_NAME not in resp.cookies
    assert VERIFY_SID_COOKIE_NAME in resp.cookies
    # Запись в email_verifications создана; письмо "отправлено".
    row = await _fetch_verification(_REG["email"])
    assert row is not None
    assert len(sent) == 1
    assert sent[0]["to"] == _REG["email"]
    assert sent[0]["code"].isdigit() and len(sent[0]["code"]) == 6
    # В БД — только хэш кода.
    assert row["code_hash"] == sha256_hex(sent[0]["code"])


@pytest.mark.asyncio
async def test_login_before_verify_forbidden(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "email_not_verified"


# --- Режим ON: verify-email --------------------------------------------------


@pytest.mark.asyncio
async def test_verify_email_correct_code(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    code = sent[0]["code"]
    resp = await client.post("/auth/verify-email", json={"email": _REG["email"], "code": code})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]
    assert REFRESH_COOKIE_NAME in resp.cookies
    # Запись верификации удалена; логин теперь проходит.
    assert await _fetch_verification(_REG["email"]) is None
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_wrong_code_increments_attempts(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    resp = await client.post("/auth/verify-email", json={"email": _REG["email"], "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_code"
    row = await _fetch_verification(_REG["email"])
    assert row is not None
    assert row["attempts"] == 1


@pytest.mark.asyncio
async def test_verify_email_too_many_attempts(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    real_code = sent[0]["code"]
    wrong = "111111" if real_code != "111111" else "222222"
    last_code = None
    for _ in range(5):
        last = await client.post("/auth/verify-email", json={"email": _REG["email"], "code": wrong})
        last_code = last.json()["error"]["code"]
    assert last_code == "too_many_attempts"
    # Запись инвалидирована — даже верный код больше не работает.
    assert await _fetch_verification(_REG["email"]) is None
    after = await client.post(
        "/auth/verify-email", json={"email": _REG["email"], "code": real_code}
    )
    assert after.status_code == 400
    assert after.json()["error"]["code"] == "invalid_code"


@pytest.mark.asyncio
async def test_verify_email_expired(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    # Просрочиваем код напрямую в БД.
    conn = await asyncpg.connect(**_DB)
    try:
        await conn.execute(
            "UPDATE email_verifications SET expires_at = $1",
            datetime.now(tz=UTC) - timedelta(minutes=1),
        )
    finally:
        await conn.close()
    resp = await client.post(
        "/auth/verify-email", json={"email": _REG["email"], "code": sent[0]["code"]}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "code_expired"


# --- Режим ON: verify-link ---------------------------------------------------


@pytest.mark.asyncio
async def test_verify_link_same_device_logs_in(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    reg = await client.post("/auth/register", json=_REG)
    sid = reg.cookies[VERIFY_SID_COOKIE_NAME]
    token = sent[0]["link_url"].split("token=")[1]
    resp = await client.post(
        "/auth/verify-link", json={"token": token}, cookies={VERIFY_SID_COOKIE_NAME: sid}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["logged_in"] is True
    assert body["access_token"]
    assert REFRESH_COOKIE_NAME in resp.cookies


@pytest.mark.asyncio
async def test_verify_link_other_device_verifies_without_login(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    token = sent[0]["link_url"].split("token=")[1]
    # Другое устройство = нет cookie dd_verify_sid. Клиент копит куки, поэтому
    # чистим jar, имитируя другой браузер.
    client.cookies.clear()
    resp = await client.post("/auth/verify-link", json={"token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["logged_in"] is False
    assert body.get("access_token") is None
    # Email при этом подтверждён → логин паролем проходит.
    login = await client.post(
        "/auth/login", json={"email": _REG["email"], "password": _REG["password"]}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_verify_link_invalid_token(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    resp = await client.post("/auth/verify-link", json={"token": "nope-not-a-real-token"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_token"


# --- Режим ON: resend --------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_generates_new_code_and_old_stops_working(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    await client.post("/auth/register", json=_REG)
    old_code = sent[0]["code"]
    # Сбрасываем sent_at, чтобы обойти троттлинг 60с.
    conn = await asyncpg.connect(**_DB)
    try:
        await conn.execute(
            "UPDATE email_verifications SET sent_at = $1",
            datetime.now(tz=UTC) - timedelta(seconds=120),
        )
    finally:
        await conn.close()
    resp = await client.post("/auth/resend-code", json={"email": _REG["email"]})
    assert resp.status_code == 204
    assert len(sent) == 2
    new_code = sent[1]["code"]
    # Старый код больше не подходит (перегенерён).
    if old_code != new_code:
        bad = await client.post(
            "/auth/verify-email", json={"email": _REG["email"], "code": old_code}
        )
        assert bad.status_code == 400
    # Новый код подтверждает.
    ok = await client.post("/auth/verify-email", json={"email": _REG["email"], "code": new_code})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_resend_unknown_email_is_204(
    client: AsyncClient, verification_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = await _captured_codes(monkeypatch)
    resp = await client.post("/auth/resend-code", json={"email": "ghost@example.com"})
    assert resp.status_code == 204
    assert sent == []  # письмо не уходит, существование не раскрывается
