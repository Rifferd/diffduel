"""Конфигурация приложения. Имена env-переменных — строго по conventions.md."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Заведомо известные dev-дефолты; прод с ними не стартует (см. валидатор ниже).
_DEV_JWT_SECRET = "dev-insecure-secret-change-me-please-0123456789-0123456789-0123456789"  # noqa: S105
_DEV_INTERNAL_TOKEN = "dev-internal-token-change-me"  # noqa: S105
_DEV_S3_SECRET = "diffduel-dev-secret"  # noqa: S105


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

    # Kafka/Redpanda — продюсер событий (duels.finished). Best-effort.
    kafka_brokers: str = "localhost:19092"

    # S3 / MinIO (presigned-аватары, см. ТЗ §3.7).
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "diffduel"
    s3_secret_key: str = _DEV_S3_SECRET
    s3_region: str = "us-east-1"
    # CDN-префикс для публичных URL; в проде — домен CDN.
    s3_public_base_url: str = "http://localhost:9000"
    s3_bucket_avatars: str = "avatars"

    # Доверять X-Forwarded-For (только когда API стоит за нашим прокси/Traefik).
    trust_proxy: bool = False

    # CORS — строго белый список origin'ов (credentials=True).
    # NoDecode: pydantic-settings иначе пытается JSON-парсить env-строку списка
    # и падает на CSV — отдаём сырую строку валидатору _split_origins ниже.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"]
    )

    sentry_dsn: str = ""

    # OpenTelemetry: если endpoint пуст — телеметрия НЕ экспортируется (no-op,
    # нулевой оверхед в проде на 4GB). Иначе OTLP/gRPC на collector.
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "diffduel-api"

    # --- Подтверждение email -------------------------------------------------
    # Фиче-флаг: OFF — регистрация авто-логинит (email_verified=true), писем нет;
    # ON — регистрация шлёт код, логин до подтверждения запрещён.
    email_verification_enabled: bool = False
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_ssl: bool = True
    smtp_starttls: bool = False
    smtp_user: str = ""
    smtp_password: str = ""  # только в .env.prod / секретах, не в репо
    smtp_from: str = "DiffDuel <verification@diffduel.com>"
    # Базовый URL SPA — для ссылки-подтверждения в письме.
    public_web_url: str = "http://localhost:5173"

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
        if self.s3_secret_key == _DEV_S3_SECRET:
            problems.append("S3_SECRET_KEY: в проде обязателен собственный секрет MinIO")
        if self.email_verification_enabled and self.email_backend == "smtp":
            if not self.smtp_host:
                problems.append("SMTP_HOST: обязателен при включённой smtp-верификации")
            if not self.smtp_user:
                problems.append("SMTP_USER: обязателен при включённой smtp-верификации")
            if not self.smtp_password:
                problems.append("SMTP_PASSWORD: обязателен при включённой smtp-верификации")
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
