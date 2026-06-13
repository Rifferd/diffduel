"""Построение ключей ZSET лидербордов и расчёт ISO-недели.

Ключи (decode_responses=True, member=str(user_id), score=elo):
- ``lb:topic:{slug}``           — топ по конкретной теме
- ``lb:weekly:{isoyear}-W{ww}`` — топ за текущую ISO-неделю (по теме-максимуму)
- ``lb:global``                 — топ по max Эло среди тем игрока
"""

from __future__ import annotations

from datetime import UTC, date, datetime

GLOBAL_KEY = "lb:global"


def topic_key(slug: str) -> str:
    return f"lb:topic:{slug}"


def weekly_key(moment: datetime | None = None) -> str:
    """Ключ недельного лидерборда для момента (по умолчанию — сейчас, UTC)."""
    moment = moment or datetime.now(tz=UTC)
    iso_year, iso_week, _ = moment.date().isocalendar()
    return f"lb:weekly:{iso_year}-W{iso_week:02d}"


def weekly_key_for_date(day: date) -> str:
    iso_year, iso_week, _ = day.isocalendar()
    return f"lb:weekly:{iso_year}-W{iso_week:02d}"
