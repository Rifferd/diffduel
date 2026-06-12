"""Тесты GET /topics, /internal/ping, /healthz, OpenAPI-видимости."""

from __future__ import annotations

import asyncpg
import pytest
from httpx import AsyncClient


async def _seed_topics() -> None:
    conn = await asyncpg.connect(
        user="diffduel",
        password="diffduel",
        database="diffduel_test",
        host="localhost",
        port=5432,
    )
    try:
        await conn.execute(
            "INSERT INTO topics (slug, title, is_active) VALUES "
            "('sql', 'SQL', true), ('python', 'Python', true), "
            "('hidden', 'Hidden', false)"
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_topics_only_active_sorted(client: AsyncClient) -> None:
    await _seed_topics()
    resp = await client.get("/topics")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.json()]
    assert slugs == ["python", "sql"]  # активные, по title


@pytest.mark.asyncio
async def test_internal_ping_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/internal/ping")).status_code == 401
    bad = await client.get("/internal/ping", headers={"X-Internal-Token": "wrong"})
    assert bad.status_code == 401
    ok = await client.get("/internal/ping", headers={"X-Internal-Token": "test-internal-token"})
    assert ok.status_code == 200
    assert ok.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_internal_not_in_openapi(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    assert not any(path.startswith("/internal") for path in schema["paths"])


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"postgres": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/topics")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'"
    assert "X-Request-ID" in resp.headers
