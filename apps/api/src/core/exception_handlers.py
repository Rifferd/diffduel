"""Регистрация единых обработчиков ошибок в формате conventions.md."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from src.core.errors import APIError
from src.core.logging import get_logger

logger = get_logger("errors")

# Сопоставление стандартных HTTP-статусов со стабильными кодами ошибок.
_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: object = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": body},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Вешает обработчики на FastAPI-приложение."""

    @app.exception_handler(APIError)
    async def _api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _error_response(
            exc.status_code,
            exc.code,
            exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422,
            "validation_error",
            "Ошибка валидации входных данных",
            details=_safe_errors(exc.errors()),
        )

    @app.exception_handler(PydanticValidationError)
    async def _pydantic_validation(_request: Request, exc: PydanticValidationError) -> JSONResponse:
        return _error_response(
            422,
            "validation_error",
            "Ошибка валидации входных данных",
            details=_safe_errors(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
        headers = dict(exc.headers) if exc.headers else None
        return _error_response(exc.status_code, code, message, headers=headers)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("internal_error", error_type=type(exc).__name__)
        return _error_response(500, "internal_error", "Внутренняя ошибка сервера")


def _safe_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, object]]:
    """Возвращает детали валидации без сырых значений (чтобы не утекали пароли)."""
    cleaned: list[dict[str, object]] = []
    for err in errors:
        cleaned.append(
            {
                "loc": err.get("loc"),
                "type": err.get("type"),
                "msg": err.get("msg"),
            }
        )
    return cleaned
