"""ORM-модели домена billing: subscriptions, payments."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.core.db_types import timestamptz, timestamptz_now, uuid_pk
from src.core.enums import PaymentPurpose, SubscriptionPlan

subscription_plan_enum = ENUM(SubscriptionPlan, name="subscription_plan", create_type=False)
payment_purpose_enum = ENUM(PaymentPurpose, name="payment_purpose", create_type=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(subscription_plan_enum, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    current_period_end: Mapped[timestamptz | None] = mapped_column(nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_sub_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    # Идемпотентность вебхуков по event_id провайдера.
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    purpose: Mapped[PaymentPurpose] = mapped_column(payment_purpose_enum, nullable=False)
    created_at: Mapped[timestamptz_now]
