"""App factory Core API: middleware, CORS, роутеры, /healthz."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.responses import JSONResponse

from src.admin.router import router as admin_router
from src.ai_review.router import router as ai_review_router
from src.auth.router import router as auth_router
from src.core.config import get_settings
from src.core.db import dispose_engine, get_sessionmaker
from src.core.events import close_producer
from src.core.exception_handlers import register_exception_handlers
from src.core.logging import configure_logging, get_logger
from src.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from src.core.redis import close_redis, get_redis
from src.core.telemetry import init_telemetry
from src.daily.router import router as daily_router
from src.internal_api.router import router as internal_router
from src.leaderboard.router import router as leaderboard_router
from src.tasks.router import router as tasks_router
from src.telegram.router import router as telegram_router
from src.topics.router import router as topics_router
from src.tournaments.admin_router import router as tournaments_admin_router
from src.tournaments.router import router as tournaments_router
from src.users.router import router as users_router

logger = get_logger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("api_starting")
    yield
    await close_producer()
    await close_redis()
    await dispose_engine()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="DiffDuel Core API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (порядок: внешний security-headers → request-context).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Observability: Sentry + OTel (traces/metrics). No-op без OTLP endpoint/DSN.
    init_telemetry(app)

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(topics_router)
    app.include_router(tasks_router)
    app.include_router(leaderboard_router)
    app.include_router(daily_router)
    app.include_router(ai_review_router)
    app.include_router(tournaments_router)
    app.include_router(admin_router)
    app.include_router(tournaments_admin_router)
    app.include_router(telegram_router)
    app.include_router(internal_router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> JSONResponse:
        """Проверяет доступность PostgreSQL и Redis."""
        checks: dict[str, str] = {}
        healthy = True

        try:
            sessionmaker = get_sessionmaker()
            async with sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception:
            logger.error("healthz_postgres_failed")
            checks["postgres"] = "error"
            healthy = False

        try:
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception:
            logger.error("healthz_redis_failed")
            checks["redis"] = "error"
            healthy = False

        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "degraded", "checks": checks},
        )

    return app


app = create_app()
