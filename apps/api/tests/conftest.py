"""Фикстуры тестов: тестовая БД diffduel_test (через alembic), Redis, httpx-клиент.

Требуется поднятый compose-стек (postgres:5432, redis:6379, diffduel/diffduel).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# Тестовое окружение задаём ДО импорта src.* (config кэширует settings).
os.environ["APP_ENV"] = "test"
_TEST_DB = "diffduel_test"
os.environ["DATABASE_URL"] = f"postgresql+asyncpg://diffduel:diffduel@localhost:5432/{_TEST_DB}"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-test-secret-0123456789"
os.environ["INTERNAL_API_TOKEN"] = "test-internal-token"
os.environ["ACCESS_TOKEN_TTL"] = "900"
os.environ["REFRESH_TOKEN_TTL"] = "2592000"

import subprocess  # noqa: E402
import sys  # noqa: E402

import asyncpg  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from src.core.redis import get_redis  # noqa: E402
from src.main import app  # noqa: E402

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _ensure_test_database() -> None:
    """Создаёт пустую БД diffduel_test (если её нет)."""
    conn = await asyncpg.connect(
        user="diffduel",
        password="diffduel",
        database="diffduel",
        host="localhost",
        port=5432,
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_DB}"')
    finally:
        await conn.close()


def _run_migrations() -> None:
    # Alembic в online-режиме сам открывает event loop (asyncio.run), поэтому
    # запускаем его отдельным процессом, чтобы не конфликтовать с loop pytest.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_PROJECT_ROOT,
        check=True,
        env={**os.environ},
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database() -> AsyncIterator[None]:
    await _ensure_test_database()
    _run_migrations()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    """Чистит таблицы и Redis перед каждым тестом."""
    redis = get_redis()
    await redis.flushdb()
    conn = await asyncpg.connect(
        user="diffduel",
        password="diffduel",
        database=_TEST_DB,
        host="localhost",
        port=5432,
    )
    try:
        await conn.execute(
            "TRUNCATE email_verifications, refresh_tokens, oauth_accounts, ratings, "
            "answers, ai_reviews, daily_challenges, duels, "
            "tournament_answers, tournament_entries, tournaments, "
            "tasks, topics, feature_flags, "
            "payments, subscriptions, users "
            "RESTART IDENTITY CASCADE"
        )
    finally:
        await conn.close()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
