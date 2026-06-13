"""Тесты конфигурации воркеров."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.workers.config import Settings


def test_defaults_dev() -> None:
    settings = Settings(app_env="dev")
    assert settings.kafka_group_id == "image-gen"
    assert settings.kafka_topic == "duels.finished"
    assert settings.s3_bucket_share_cards == "share-cards"


def test_prod_rejects_dev_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="prod")


def test_prod_ok_with_real_secrets() -> None:
    settings = Settings(
        app_env="prod",
        internal_api_token="x" * 40,
        s3_secret_key="real-minio-secret",
    )
    assert settings.app_env == "prod"


def test_empty_brokers_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(kafka_brokers="  ")
