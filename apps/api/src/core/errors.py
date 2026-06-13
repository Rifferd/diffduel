"""Единый формат ошибок API: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

from typing import Any


class APIError(Exception):
    """Базовая доменная ошибка с устойчивым кодом (контракт фронта)."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        self.headers = headers

    def to_payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            body["details"] = self.details
        return {"error": body}


class ValidationError(APIError):
    status_code = 422
    code = "validation_error"


class BadRequestError(APIError):
    status_code = 400
    code = "bad_request"


class AuthError(APIError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class RateLimitedError(APIError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(APIError):
    status_code = 503
    code = "service_unavailable"
