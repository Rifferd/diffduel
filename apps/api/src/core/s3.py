"""Async S3-клиент (MinIO в dev) для presigned-флоу аватаров (ТЗ §3.7).

Тонкая обёртка над aioboto3: ленивая сессия + контекстный клиент на операцию.
Файлы НЕ проходят через API — клиент грузит напрямую в MinIO по presigned PUT.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config import get_settings

if TYPE_CHECKING:
    from types_aiobotocore_s3.client import S3Client
else:
    S3Client = Any

_session: aioboto3.Session | None = None

# Подпись presigned-URL версии 4 — обязательна для MinIO/S3.
_BOTO_CONFIG = Config(signature_version="s3v4")


def _get_session() -> aioboto3.Session:
    """Ленивая инициализация сессии (одна на процесс)."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


@asynccontextmanager
async def s3_client() -> AsyncIterator[S3Client]:
    """Контекстный async S3-клиент с кредами из env (S3_*)."""
    settings = get_settings()
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=_BOTO_CONFIG,
    ) as client:
        yield client


async def presigned_put_url(
    *,
    bucket: str,
    key: str,
    content_type: str,
    expires_in: int,
) -> str:
    """Presigned PUT URL с зашитым в подпись Content-Type.

    Зашитый Content-Type означает, что клиент обязан прислать ровно тот тип,
    который мы валидировали, иначе подпись не сойдётся.
    """
    async with s3_client() as client:
        url: str = await client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url


class S3ObjectHead:
    """Результат HEAD объекта (метаданные без тела)."""

    __slots__ = ("content_length", "content_type")

    def __init__(self, *, content_length: int, content_type: str | None) -> None:
        self.content_length = content_length
        self.content_type = content_type


async def head_object(*, bucket: str, key: str) -> S3ObjectHead | None:
    """HEAD объекта. Возвращает None, если объекта нет (404/NoSuchKey)."""
    async with s3_client() as client:
        try:
            resp = await client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NoSuchBucket"}:
                return None
            raise
        return S3ObjectHead(
            content_length=int(resp.get("ContentLength", 0)),
            content_type=resp.get("ContentType"),
        )


async def delete_object(*, bucket: str, key: str) -> None:
    """Best-effort удаление объекта (ошибки гасятся вызывающим)."""
    async with s3_client() as client:
        await client.delete_object(Bucket=bucket, Key=key)
