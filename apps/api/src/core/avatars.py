"""Сборка публичного URL аватара.

Единый хелпер, чтобы формат `S3_PUBLIC_BASE_URL/{bucket}/{key}` не дублировался
между users и leaderboard.
"""

from __future__ import annotations

from src.core.config import get_settings


def avatar_url(avatar_key: str | None) -> str | None:
    """Публичный URL аватара: S3_PUBLIC_BASE_URL/avatars/{key} (или None)."""
    if not avatar_key:
        return None
    settings = get_settings()
    base = settings.s3_public_base_url.rstrip("/")
    return f"{base}/{settings.s3_bucket_avatars}/{avatar_key}"
