"""Загрузка PNG-карточки в MinIO (S3) bucket ``share-cards`` через aioboto3.

Бакет уже настроен как public-read (conventions.md), поэтому ACL не выставляем —
объект доступен по ``{S3_PUBLIC_BASE_URL}/share-cards/{duel_id}.png``.
"""

from __future__ import annotations

import aioboto3

from src.workers.config import Settings
from src.workers.logging import get_logger

logger = get_logger("storage")


class CardStorage:
    """Тонкая обёртка над aioboto3 S3-клиентом для аплоада карточек."""

    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.s3_endpoint
        self._access_key = settings.s3_access_key
        self._secret_key = settings.s3_secret_key
        self._region = settings.s3_region
        self._bucket = settings.s3_bucket_share_cards
        self._session = aioboto3.Session()

    @staticmethod
    def key_for(duel_id: str) -> str:
        """Ключ объекта в бакете: ``{duel_id}.png``."""
        return f"{duel_id}.png"

    async def upload_card(self, duel_id: str, png: bytes) -> str:
        """Грузит PNG и возвращает ключ объекта. Бросает при ошибке S3."""
        key = self.key_for(duel_id)
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
        ) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=png,
                ContentType="image/png",
            )
        logger.info("share_card_uploaded", duel_id=duel_id, key=key, bytes=len(png))
        return key
