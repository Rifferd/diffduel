"""Абстракция платёжного провайдера (Protocol) и его контрактные типы.

``PaymentProvider`` — единый интерфейс под ЮKassa/Stripe/заглушку. Эндпоинты и
сервисы billing зависят ТОЛЬКО от этого Protocol, не зная конкретного провайдера
(подменяется в DI). Реальные провайдеры в MVP не реализованы — см. ManualProvider.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from src.core.enums import PaymentPurpose
from src.users.models import User


class ProductCode(StrEnum):
    """Продукты, доступные к покупке."""

    pro_monthly = "pro_monthly"


@dataclass(slots=True, frozen=True)
class Product:
    """Описание продаваемого продукта (цена/валюта/назначение платежа)."""

    code: ProductCode
    amount: Decimal
    currency: str
    purpose: PaymentPurpose
    # Сколько дней Pro выдаётся за продукт (для подписочных продуктов).
    pro_days: int


@dataclass(slots=True, frozen=True)
class CheckoutResult:
    """Результат инициации оплаты.

    ``checkout_url`` — куда редиректить пользователя (None у заглушки).
    ``status`` — pending у реального провайдера; unavailable у заглушки.
    ``message`` — человекочитаемое пояснение (для unavailable).
    """

    status: str
    checkout_url: str | None
    message: str
    provider: str


@runtime_checkable
class PaymentProvider(Protocol):
    """Контракт провайдера оплаты."""

    name: str

    async def create_checkout(self, user: User, product: Product) -> CheckoutResult:
        """Инициирует оплату продукта пользователем."""
        ...
