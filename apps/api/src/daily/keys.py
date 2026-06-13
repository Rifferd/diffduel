"""Ключи Redis ZSET дневного лидерборда: ``lb:daily:{YYYY-MM-DD}``."""

from __future__ import annotations

from datetime import date


def daily_key(day: date) -> str:
    return f"lb:daily:{day.isoformat()}"
