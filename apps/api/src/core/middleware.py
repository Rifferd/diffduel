"""Сквозные middleware: request_id (structlog) и security-заголовки."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.core.logging import get_logger

logger = get_logger("http")

# CSP для API: контент не предполагается, поэтому всё запрещено.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Привязывает request_id к контексту логов и кладёт его в заголовок ответа."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_exception")
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info("request_completed", status_code=response.status_code)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Добавляет защитные заголовки во все ответы."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
