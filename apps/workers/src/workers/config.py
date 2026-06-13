"""Конфигурация воркеров. Имена env-переменных — строго по conventions.md."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Заведомо известный dev-дефолт; прод с ним не стартует (см. валидатор ниже).
_DEV_INTERNAL_TOKEN = "dev-internal-token-change-me"  # noqa: S105
_DEV_S3_SECRET = "diffduel-dev-secret"  # noqa: S105


class Settings(BaseSettings):
    """Настройки воркеров, читаются из окружения (.env не коммитится)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["dev", "test", "prod"] = "dev"

    # Kafka/Redpanda — консьюмер duels.finished.
    kafka_brokers: str = "localhost:19092"
    kafka_group_id: str = "image-gen"
    kafka_topic: str = "duels.finished"

    # S3 / MinIO — публичный бакет share-карточек.
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "diffduel"
    s3_secret_key: str = _DEV_S3_SECRET
    s3_region: str = "us-east-1"
    s3_bucket_share_cards: str = "share-cards"

    # Core API internal-эндпоинт.
    core_api_url: str = "http://localhost:8000"
    internal_api_token: str = _DEV_INTERNAL_TOKEN
    internal_timeout_s: float = 5.0
    internal_max_retries: int = 2  # всего попыток = 1 + retries

    # Обработка одного события: сколько раз ретраить рендер/аплоад до пропуска
    # «ядовитого» сообщения (защита от вечного зависания консьюмера).
    process_max_attempts: int = 3

    # Бэкофф переподключения к брокеру на старте (секунды).
    broker_connect_backoff_s: float = 1.0
    broker_connect_backoff_max_s: float = 30.0

    # AI-разбор (ai-review консьюмер). Топик/group отдельные от image-gen.
    ai_review_topic: str = "ai.review.requested"
    ai_review_group_id: str = "ai-review"
    # Anthropic SDK: ключ пуст → разбор недоступен (пишем failed).
    anthropic_api_key: str = ""
    # Точная строка без date-суффикса (claude-api справочник).
    ai_review_model: str = "claude-opus-4-8"
    ai_review_max_tokens: int = 4000

    # Observability. Пусто = выключено (no-op, нулевой оверхед в проде).
    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "diffduel-workers"

    @field_validator("kafka_brokers")
    @classmethod
    def _non_empty_brokers(cls, value: str, /) -> str:
        if not value.strip():
            raise ValueError("KAFKA_BROKERS не может быть пустым")
        return value

    @model_validator(mode="after")
    def _forbid_dev_secrets_in_prod(self) -> Settings:
        """Прод с dev-секретами не должен подняться — fail fast на старте."""
        if self.app_env != "prod":
            return self
        problems: list[str] = []
        if self.internal_api_token == _DEV_INTERNAL_TOKEN or len(self.internal_api_token) < 32:
            problems.append("INTERNAL_API_TOKEN: в проде обязателен случайный токен >=32 символов")
        if self.s3_secret_key == _DEV_S3_SECRET:
            problems.append("S3_SECRET_KEY: в проде обязателен собственный секрет MinIO")
        if problems:
            raise ValueError("; ".join(problems))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшированный синглтон настроек."""
    return Settings()
