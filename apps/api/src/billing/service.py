"""Бизнес-логика billing: Pro-статус, ручная выдача/отзыв Pro через админку.

Pro-статус — производное от таблицы subscriptions (plan='pro', status='active',
current_period_end > now). Реального провайдера нет — выдача только админом:
grant-pro продлевает активную подписку на N дней (или создаёт новую), пишет
payment purpose='subscription' provider='manual'.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.repository import ACTIVE, BillingRepository
from src.billing.schemas import ProStatus
from src.core.enums import PaymentPurpose
from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.users.models import User
from src.users.repository import UserRepository

logger = get_logger("billing")

_MANUAL_PROVIDER = "manual"
# Ручная выдача — нулевой «платёж» (запись для аудита, не реальные деньги).
_MANUAL_AMOUNT = Decimal("0.00")
_MANUAL_CURRENCY = "RUB"


async def is_pro(session: AsyncSession, user: User, *, now: datetime | None = None) -> bool:
    """True, если у пользователя активная Pro-подписка с непрошедшим сроком."""
    moment = now or datetime.now(tz=UTC)
    sub = await BillingRepository(session).active_pro_subscription(user.id, now=moment)
    return sub is not None


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BillingRepository(session)
        self._users = UserRepository(session)

    async def grant_pro(self, user_id: uuid.UUID, *, days: int) -> ProStatus:
        """Выдаёт/продлевает Pro на ``days`` дней. Идемпотентно-безопасно.

        Если есть активная подписка — продлеваем от её current_period_end;
        иначе — от now (новая подписка). Пишем audit-платёж 'manual'.
        """
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден", code="user_not_found")

        now = datetime.now(tz=UTC)
        existing = await self._repo.latest_pro_subscription(user_id)
        # База продления: непрошедший срок активной подписки, иначе now.
        if (
            existing is not None
            and existing.status == ACTIVE
            and existing.current_period_end is not None
            and existing.current_period_end > now
        ):
            new_end = existing.current_period_end + timedelta(days=days)
            existing.current_period_end = new_end
            existing.status = ACTIVE
        else:
            new_end = now + timedelta(days=days)
            self._repo.add_subscription(
                user_id=user_id, current_period_end=new_end, provider=_MANUAL_PROVIDER
            )

        self._repo.add_payment(
            user_id=user_id,
            amount=_MANUAL_AMOUNT,
            currency=_MANUAL_CURRENCY,
            provider=_MANUAL_PROVIDER,
            # Уникальный event_id заглушки — для идемпотентности схемы payments.
            provider_event_id=f"manual:grant:{uuid.uuid4()}",
            purpose=PaymentPurpose.subscription,
        )
        await self._session.commit()
        logger.info("pro_granted", user_id=str(user_id), days=days)
        return ProStatus(is_pro=True, current_period_end=new_end)

    async def revoke_pro(self, user_id: uuid.UUID) -> ProStatus:
        """Отзывает Pro: помечает активную подписку cancelled. Идемпотентно."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден", code="user_not_found")

        now = datetime.now(tz=UTC)
        sub = await self._repo.active_pro_subscription(user_id, now=now)
        if sub is not None:
            sub.status = "cancelled"
            sub.current_period_end = now
        await self._session.commit()
        logger.info("pro_revoked", user_id=str(user_id))
        return ProStatus(is_pro=False, current_period_end=None)
