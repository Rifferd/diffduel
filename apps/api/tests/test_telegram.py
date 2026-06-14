"""Интеграционные тесты привязки Telegram и SVG-виджета рейтинга (Релиз 3, A).

Покрытие:
- link-code: генерит код в Redis (TTL), bot_url из TELEGRAM_BOT_USERNAME;
- redeem: валид / невалид / повтор (одноразовость);
- resolve: linked / 404;
- DELETE: отвязка;
- виджет: валидный SVG с корректными данными + нейтральный для несуществующего (200);
- internal: X-Internal-Token обязателен.
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.core.config import get_settings
from src.core.redis import get_redis
from src.core.security import create_access_token

_TOKEN = {"X-Internal-Token": "test-internal-token"}
_DB = {
    "user": "diffduel",
    "password": "diffduel",
    "database": "diffduel_test",
    "host": "localhost",
    "port": 5432,
}


@pytest_asyncio.fixture
async def bot_username() -> AsyncIterator[str]:
    """Включает TELEGRAM_BOT_USERNAME на время теста."""
    settings = get_settings()
    original = settings.telegram_bot_username
    object.__setattr__(settings, "telegram_bot_username", "diffduel_bot")
    try:
        yield "diffduel_bot"
    finally:
        object.__setattr__(settings, "telegram_bot_username", original)


async def _make_user(suffix: str, *, banned: bool = False) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        uid = await conn.fetchval(
            "INSERT INTO users (email, username) VALUES ($1, $2) RETURNING id",
            f"{suffix}@example.com",
            f"user_{suffix}",
        )
        if banned:
            await conn.execute("UPDATE users SET banned_at = now() WHERE id = $1", uid)
        return uuid.UUID(str(uid))
    finally:
        await conn.close()


async def _topic_id(slug: str) -> uuid.UUID:
    conn = await asyncpg.connect(**_DB)
    try:
        row = await conn.fetchval(
            "INSERT INTO topics (slug, title) VALUES ($1, $2) RETURNING id", slug, slug.upper()
        )
        return uuid.UUID(str(row))
    finally:
        await conn.close()


async def _set_rating(user_id: uuid.UUID, topic_id: uuid.UUID, elo: int) -> None:
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


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# --- link-code ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_link_code_stores_in_redis_with_bot_url(
    client: AsyncClient, bot_username: str
) -> None:
    uid = await _make_user("lc")
    resp = await client.post("/me/telegram/link-code", headers=_auth(uid))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    code = body["code"]
    assert code and body["bot_url"] == f"https://t.me/{bot_username}?start={code}"

    redis = get_redis()
    assert await redis.get(f"tg:link:{code}") == str(uid)
    ttl = await redis.ttl(f"tg:link:{code}")
    assert 0 < ttl <= 600


@pytest.mark.asyncio
async def test_link_code_without_bot_username(client: AsyncClient) -> None:
    uid = await _make_user("lcnob")
    resp = await client.post("/me/telegram/link-code", headers=_auth(uid))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"]
    assert body["bot_url"] is None


@pytest.mark.asyncio
async def test_link_code_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/me/telegram/link-code")
    assert resp.status_code == 401


# --- redeem -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redeem_valid(client: AsyncClient) -> None:
    uid = await _make_user("rd")
    code = (await client.post("/me/telegram/link-code", headers=_auth(uid))).json()["code"]

    resp = await client.post(
        "/internal/telegram/redeem",
        json={"code": code, "telegram_user_id": 555},
        headers=_TOKEN,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"user_id": str(uid), "username": "user_rd"}
    # Код одноразовый — удалён из Redis.
    assert await get_redis().get(f"tg:link:{code}") is None


@pytest.mark.asyncio
async def test_redeem_invalid_code(client: AsyncClient) -> None:
    resp = await client.post(
        "/internal/telegram/redeem",
        json={"code": "NOPECODE", "telegram_user_id": 1},
        headers=_TOKEN,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_link_code"


@pytest.mark.asyncio
async def test_redeem_twice_fails_second(client: AsyncClient) -> None:
    uid = await _make_user("rd2")
    code = (await client.post("/me/telegram/link-code", headers=_auth(uid))).json()["code"]

    first = await client.post(
        "/internal/telegram/redeem",
        json={"code": code, "telegram_user_id": 777},
        headers=_TOKEN,
    )
    assert first.status_code == 200
    second = await client.post(
        "/internal/telegram/redeem",
        json={"code": code, "telegram_user_id": 777},
        headers=_TOKEN,
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_redeem_requires_internal_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/internal/telegram/redeem",
        json={"code": "X", "telegram_user_id": 1},
    )
    assert resp.status_code == 401


# --- resolve ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_linked(client: AsyncClient) -> None:
    uid = await _make_user("res")
    code = (await client.post("/me/telegram/link-code", headers=_auth(uid))).json()["code"]
    await client.post(
        "/internal/telegram/redeem",
        json={"code": code, "telegram_user_id": 999},
        headers=_TOKEN,
    )

    resp = await client.get("/internal/telegram/user/999", headers=_TOKEN)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"user_id": str(uid), "username": "user_res", "linked": True}


@pytest.mark.asyncio
async def test_resolve_not_found(client: AsyncClient) -> None:
    resp = await client.get("/internal/telegram/user/123456", headers=_TOKEN)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_requires_internal_token(client: AsyncClient) -> None:
    resp = await client.get("/internal/telegram/user/1")
    assert resp.status_code == 401


# --- unlink -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unlink(client: AsyncClient) -> None:
    uid = await _make_user("ul")
    code = (await client.post("/me/telegram/link-code", headers=_auth(uid))).json()["code"]
    await client.post(
        "/internal/telegram/redeem",
        json={"code": code, "telegram_user_id": 4242},
        headers=_TOKEN,
    )

    resp = await client.delete("/me/telegram", headers=_auth(uid))
    assert resp.status_code == 204
    # После отвязки resolve больше не находит.
    assert (await client.get("/internal/telegram/user/4242", headers=_TOKEN)).status_code == 404


@pytest.mark.asyncio
async def test_unlink_idempotent(client: AsyncClient) -> None:
    uid = await _make_user("uli")
    resp = await client.delete("/me/telegram", headers=_auth(uid))
    assert resp.status_code == 204


# --- widget -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_widget_valid_svg_with_data(client: AsyncClient) -> None:
    uid = await _make_user("wg")
    tid = await _topic_id("wg_topic")
    await _set_rating(uid, tid, 1480)

    resp = await client.get("/widget/user_wg.svg")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.headers["cache-control"] == "public, max-age=300"

    # Валидный XML/SVG.
    root = ET.fromstring(resp.text)  # noqa: S314 — парсим наш же сгенерированный SVG
    assert root.tag.endswith("svg")
    assert "1480" in resp.text
    assert "user_wg" in resp.text
    # Без JS.
    assert "<script" not in resp.text.lower()


@pytest.mark.asyncio
async def test_widget_not_found_is_neutral_200(client: AsyncClient) -> None:
    resp = await client.get("/widget/ghost.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    root = ET.fromstring(resp.text)  # noqa: S314 — парсим наш же сгенерированный SVG
    assert root.tag.endswith("svg")
    assert "<script" not in resp.text.lower()


@pytest.mark.asyncio
async def test_widget_banned_is_neutral_200(client: AsyncClient) -> None:
    await _make_user("banned_wg", banned=True)
    resp = await client.get("/widget/user_banned_wg.svg")
    assert resp.status_code == 200
    # Забаненного не светим: его ника нет в нейтральном бейдже.
    assert "user_banned_wg" not in resp.text
