"""Конфигурация приложения. Имена env-переменных — строго по conventions.md."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Заведомо известные dev-дефолты; прод с ними не стартует (см. валидатор ниже).
_DEV_JWT_SECRET = "dev-insecure-secret-change-me-please-0123456789-0123456789-0123456789"  # noqa: S105
_DEV_INTERNAL_TOKEN = "dev-internal-token-change-me"  # noqa: S105


class Settings(BaseSettings):
    """Настройки Core API, читаются из окружения (.env не коммитится)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["dev", "test", "prod"] = "dev"

    # Postgres / Redis.
    database_url: str = "postgresql+asyncpg://diffduel:diffduel@localhost:5432/diffduel"
    redis_url: str = "redis://localhost:6379/0"

    # JWT / refresh.
    jwt_secret: str = Field(default=_DEV_JWT_SECRET)
    access_token_ttl: int = 900  # секунды
    refresh_token_ttl: int = 2_592_000  # 30 дней, секунды

    # Internal API.
    internal_api_token: str = _DEV_INTERNAL_TOKEN

    # Доверять X-Forwarded-For (только когда API стоит за нашим прокси/Traefik).
    trust_proxy: bool = False

    # CORS — строго белый список origin'ов (credentials=True).
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"]
    )

    sentry_dsn: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Позволяет задавать CORS_ORIGINS как CSV-строку в env."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _check_secret_len(cls, value: str, /) -> str:
        # В проде секрет обязан быть длинным; в dev/test допускаем дефолт.
        if len(value) < 32:
            raise ValueError("JWT_SECRET должен быть не короче 32 символов")
        return value

    @model_validator(mode="after")
    def _forbid_dev_secrets_in_prod(self) -> Settings:
        """Прод с dev-секретами не должен подняться вообще — fail fast на старте."""
        if self.app_env != "prod":
            return self
        problems: list[str] = []
        if self.jwt_secret == _DEV_JWT_SECRET or len(self.jwt_secret) < 64:
            problems.append("JWT_SECRET: в проде обязателен случайный секрет >=64 символов")
        if self.internal_api_token == _DEV_INTERNAL_TOKEN or len(self.internal_api_token) < 32:
            problems.append("INTERNAL_API_TOKEN: в проде обязателен случайный токен >=32 символов")
        if any(origin.startswith("http://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS: в проде допускаются только https-origin'ы")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def cookie_secure(self) -> bool:
        """В dev/test разрешаем не-Secure cookie, чтобы тесты по http работали."""
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшированный синглтон настроек."""
    return Settings()
