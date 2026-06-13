"""Платёжные провайдеры billing.

Реальный провайдер (ЮKassa/Stripe) НЕ реализован — структура готова под него.
В MVP активна только заглушка ``ManualProvider``: оплата выдаётся вручную через
админку (grant-pro), реальный checkout недоступен.
"""

from __future__ import annotations

from src.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    Product,
)
from src.billing.providers.manual import ManualProvider

__all__ = [
    "CheckoutResult",
    "ManualProvider",
    "PaymentProvider",
    "Product",
]
