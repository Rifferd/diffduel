"""structlog: JSON-логи. Чувствительные поля (пароли, токены) не логируются."""

from __future__ import annotations

import logging
import sys

import structlog

# Поля, которые ни при каких условиях не попадают в логи.
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "refresh_token",
        "access_token",
        "authorization",
        "cookie",
        "set-cookie",
        "x-internal-token",
        "jwt_secret",
    }
)


def _redact_sensitive(
    _logger: object, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Маскирует чувствительные ключи в любом месте event_dict."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***"
    return event_dict


def configure_logging() -> None:
    """Настраивает structlog на структурированный JSON-вывод в stdout."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_sensitive,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Возвращает связанный логгер."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
