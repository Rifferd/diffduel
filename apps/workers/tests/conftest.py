"""Фикстуры тестов воркеров. Юнит-тесты не требуют compose-стека."""

from __future__ import annotations

import os

# Тестовое окружение задаём ДО импорта src.* (config кэширует settings).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal-token")
