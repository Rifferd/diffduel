"""Заглушка провайдера оплаты: реального checkout нет, Pro выдаёт админ вручную.

В MVP платёжный шлюз не подключён. ``create_checkout`` не создаёт реального
платежа и не редиректит — возвращает status="unavailable" с пояснением, что
оплата выдаётся через администратора (grant-pro). Структура готова под замену
на реальный провайдер без изменения вызывающего кода.
"""

from __future__ import annotations

from src.billing.providers.base import CheckoutResult, Product
from src.users.models import User


class ManualProvider:
    """Ручной провайдер: оплата недоступна, Pro выдаётся админкой."""

    name = "manual"

    async def create_checkout(self, user: User, product: Product) -> CheckoutResult:
        return CheckoutResult(
            status="unavailable",
            checkout_url=None,
            message="Онлайн-оплата временно недоступна, обратитесь к администратору.",
            provider=self.name,
        )
