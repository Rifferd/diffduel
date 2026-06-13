"""Бизнес-логика домена users."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.service import is_pro
from src.core import s3
from src.core.avatars import avatar_url
from src.core.config import get_settings
from src.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from src.core.logging import get_logger
from src.users.models import User
from src.users.repository import UserRepository
from src.users.schemas import (
    AVATAR_CONTENT_TYPES,
    MAX_AVATAR_SIZE_BYTES,
    AvatarPresignRequest,
    AvatarPresignResponse,
    TopicAccuracy,
    TopicRating,
    UserProfile,
    UserStats,
    UserUpdate,
)

logger = get_logger("users")

# TTL presigned-URL загрузки аватара — 5 минут (ТЗ §3.7).
_AVATAR_UPLOAD_TTL_S = 300


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._settings = get_settings()

    async def update_me(self, user: User, data: UserUpdate) -> User:
        if data.username is not None and data.username != user.username:
            if await self._users.exists_username(data.username):
                raise ConflictError("Username уже занят", code="username_taken")
            try:
                await self._users.update_username(user, data.username)
            except IntegrityError as exc:
                raise ConflictError("Username уже занят", code="username_taken") from exc
        return user

    # --- Публичный профиль ---------------------------------------------------

    async def public_profile(self, username: str) -> UserProfile:
        """Профиль по username. Забаненный/несуществующий → 404."""
        user = await self._users.get_by_username(username)
        if user is None or user.banned_at is not None:
            raise NotFoundError("Пользователь не найден", code="user_not_found")

        topics = await self._users.topic_ratings(user.id)
        stats = await self._users.profile_stats(user.id)
        win_rate = round(stats.wins / stats.total_duels, 4) if stats.total_duels else 0.0
        return UserProfile(
            username=user.username,
            avatar_url=avatar_url(user.avatar_key),
            created_at=user.created_at,
            is_pro=await is_pro(self._session, user),
            topics=[TopicRating(slug=t.slug, title=t.title, elo=t.elo) for t in topics],
            total_duels=stats.total_duels,
            wins=stats.wins,
            win_rate=win_rate,
            streak=stats.streak,
        )

    # --- Расширенная статистика (Pro-функция) --------------------------------

    async def extended_stats(self, user: User, *, period_days: int) -> UserStats:
        """Полная статистика точности по темам за period (только Pro — гейт в роутере)."""
        since = datetime.now(tz=UTC) - timedelta(days=period_days)
        rows = await self._users.topic_accuracy_since(user.id, since=since)
        topics = [
            TopicAccuracy(
                slug=r.slug,
                title=r.title,
                answered=r.answered,
                correct=r.correct,
                accuracy=round(r.correct / r.answered, 4) if r.answered else 0.0,
                avg_time_ms=r.avg_time_ms,
            )
            for r in rows
        ]
        total_answered = sum(r.answered for r in rows)
        total_correct = sum(r.correct for r in rows)
        overall = round(total_correct / total_answered, 4) if total_answered else 0.0
        return UserStats(
            period_days=period_days,
            total_answered=total_answered,
            total_correct=total_correct,
            overall_accuracy=overall,
            topics=topics,
        )

    # --- Аватары (presigned flow, ТЗ §3.7) ----------------------------------

    async def presign_avatar(self, user: User, data: AvatarPresignRequest) -> AvatarPresignResponse:
        ext = AVATAR_CONTENT_TYPES[data.content_type]
        key = f"{user.id}/{uuid.uuid4()}.{ext}"
        url = await s3.presigned_put_url(
            bucket=self._settings.s3_bucket_avatars,
            key=key,
            content_type=data.content_type,
            expires_in=_AVATAR_UPLOAD_TTL_S,
        )
        return AvatarPresignResponse(upload_url=url, key=key, expires_in=_AVATAR_UPLOAD_TTL_S)

    async def confirm_avatar(self, user: User, key: str) -> User:
        # Ключ обязан принадлежать пользователю — иначе подмена чужого пути.
        if not key.startswith(f"{user.id}/"):
            raise ForbiddenError("Ключ не принадлежит пользователю", code="avatar_key_forbidden")

        head = await s3.head_object(bucket=self._settings.s3_bucket_avatars, key=key)
        if head is None:
            raise ValidationError("Объект не загружен", code="avatar_not_uploaded")
        if head.content_length > MAX_AVATAR_SIZE_BYTES:
            raise ValidationError("Файл превышает 2 МБ", code="avatar_too_large")
        if head.content_type not in AVATAR_CONTENT_TYPES:
            raise ValidationError("Недопустимый content-type", code="avatar_bad_content_type")

        old_key = user.avatar_key
        await self._users.update_avatar_key(user, key)

        # Старый объект удаляем best-effort — провал не должен ломать запрос.
        if old_key and old_key != key:
            try:
                await s3.delete_object(bucket=self._settings.s3_bucket_avatars, key=old_key)
            except Exception:
                logger.warning("avatar_old_delete_failed", key=old_key)

        return user
