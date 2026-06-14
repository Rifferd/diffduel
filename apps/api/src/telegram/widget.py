"""Embeddable SVG-виджет рейтинга для README на GitHub.

GET /widget/{username}.svg — публичный бейдж: ник, глобальный Эло, винрейт.
Чистый SVG без JS. Несуществующий/забаненный пользователь → нейтральный
бейдж «not found» с HTTP 200 (чтобы README не ломался).

Глобальный Эло = max Эло среди тем игрока (как lb:global, см. leaderboard).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import Rating, User
from src.users.repository import UserRepository

# Бренд DiffDuel (цвета токенов дизайна).
_BG = "#0d1117"
_ACCENT = "#7c5cff"
_TEXT = "#e6edf3"
_MUTED = "#8b949e"
_NEUTRAL_ACCENT = "#30363d"

# Дефолтный Эло для игрока без сыгранных тем (как server_default ratings.elo).
_DEFAULT_ELO = 1200


@dataclass(slots=True, frozen=True)
class WidgetData:
    username: str
    elo: int
    winrate: int  # проценты, 0..100


async def _global_elo(session: AsyncSession, user_id: uuid.UUID) -> int:
    """max Эло среди тем игрока (как lb:global). Нет тем → дефолт 1200."""
    stmt = select(func.max(Rating.elo)).where(Rating.user_id == user_id)
    value = (await session.execute(stmt)).scalar_one_or_none()
    return int(value) if value is not None else _DEFAULT_ELO


async def load_widget_data(session: AsyncSession, username: str) -> WidgetData | None:
    """Собирает данные виджета. Несуществующий/забаненный → None."""
    users = UserRepository(session)
    user: User | None = await users.get_by_username(username)
    if user is None or user.banned_at is not None:
        return None

    elo = await _global_elo(session, user.id)
    stats = await users.profile_stats(user.id)
    winrate = round(stats.wins * 100 / stats.total_duels) if stats.total_duels else 0
    return WidgetData(username=user.username, elo=elo, winrate=winrate)


def _escape(text: str) -> str:
    """Экранирует текст для безопасной вставки в SVG (XML)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _badge(*, title: str, fields: list[tuple[str, str]], accent: str) -> str:
    """Собирает SVG-бейдж: заголовок + строки «label: value». Чистый SVG, без JS."""
    width = 320
    height = 120
    rows = ""
    y = 74
    for label, value in fields:
        rows += (
            f'<text x="20" y="{y}" font-size="14" fill="{_MUTED}" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{_escape(label)}</text>'
            f'<text x="300" y="{y}" font-size="14" font-weight="700" fill="{_TEXT}" '
            f'text-anchor="end" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{_escape(value)}</text>'
        )
        y += 26

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="DiffDuel: {_escape(title)}">'
        f'<rect width="{width}" height="{height}" rx="10" fill="{_BG}"/>'
        f'<rect width="6" height="{height}" rx="3" fill="{accent}"/>'
        f'<text x="20" y="34" font-size="18" font-weight="700" fill="{accent}" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">DiffDuel</text>'
        f'<text x="20" y="52" font-size="13" fill="{_TEXT}" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{_escape(title)}</text>'
        f"{rows}"
        f"</svg>"
    )


def render_widget(data: WidgetData) -> str:
    """SVG-бейдж рейтинга пользователя."""
    return _badge(
        title=f"@{data.username}",
        fields=[
            ("Глобальный Эло", str(data.elo)),
            ("Винрейт", f"{data.winrate}%"),
        ],
        accent=_ACCENT,
    )


def render_not_found() -> str:
    """Нейтральный бейдж для несуществующего/забаненного пользователя (HTTP 200)."""
    return _badge(
        title="игрок не найден",
        fields=[("Статус", "—")],
        accent=_NEUTRAL_ACCENT,
    )
