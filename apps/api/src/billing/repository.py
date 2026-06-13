"""Доступ к данным billing: подписки и платежи."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.models import Payment, Subscription
from src.core.enums import PaymentPurpose, SubscriptionPlan

# Статус активной подписки.
ACTIVE = "active"


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_pro_subscription(
        self, user_id: uuid.UUID, *, now: datetime
    ) -> Subscription | None:
        """Активная Pro-подписка с current_period_end > now (или без срока)."""
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.plan == SubscriptionPlan.pro,
            Subscription.status == ACTIVE,
            Subscription.current_period_end > now,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def latest_pro_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Последняя Pro-подписка пользователя (для продления grant-pro)."""
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.plan == SubscriptionPlan.pro,
            )
            .order_by(Subscription.current_period_end.desc().nullslast())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    def add_subscription(
        self,
        *,
        user_id: uuid.UUID,
        current_period_end: datetime,
        provider: str,
    ) -> Subscription:
        sub = Subscription(
            user_id=user_id,
            plan=SubscriptionPlan.pro,
            status=ACTIVE,
            current_period_end=current_period_end,
            provider=provider,
        )
        self._session.add(sub)
        return sub

    def add_payment(
        self,
        *,
        user_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        provider: str,
        provider_event_id: str,
        purpose: PaymentPurpose,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            status="succeeded",
            provider=provider,
            provider_event_id=provider_event_id,
            purpose=purpose,
        )
        self._session.add(payment)
        return payment
