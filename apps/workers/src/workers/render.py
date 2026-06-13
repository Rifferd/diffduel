"""Рендер share-карточки результата дуэли (Pillow, чистая функция).

Вход — :class:`CardData` (dataclass), выход — ``bytes`` PNG 1200×630 (OG-формат).
Без сети и I/O кроме чтения бандла шрифтов: тестируется юнитом.

Дизайн — §13 / leaderboards-admin.md §C:
- диагональный VS-сплит (наклонная линия ≈78°): зелёная половина победителя,
  красная — проигравшего; ничья — нейтральные серые тона;
- ник победителя, счёт, дельты Эло (``+24`` / ``−18``) — все цифры моноширинным;
- обязательный водяной знак ``diffduel.com`` (нижний угол).

Цвета захардкожены из packages/ui-tokens/tokens.css (ссылка на токен в комментарии).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

# — размеры карточки (OG) —
WIDTH = 1200
HEIGHT = 630

# — цвета из packages/ui-tokens/tokens.css (single source of truth) —
_SHARE_PLUS = (0x15, 0x30, 0x1F)  # --share-plus  : тёмно-зелёная половина победителя
_SHARE_MINUS = (0x37, 0x1B, 0x1D)  # --share-minus : тёмно-красная половина проигравшего
_SHARE_DRAW_L = (0x25, 0x30, 0x3B)  # --share-draw-l: ничья, левая половина
_SHARE_DRAW_R = (0x2C, 0x25, 0x30)  # --share-draw-r: ничья, правая половина
_PLUS_BRIGHT = (0x4F, 0xCB, 0x82)  # --plus-bright : "+" на тёмном
_MINUS_BRIGHT = (0xFF, 0x7B, 0x81)  # --minus-bright: "−" на тёмном
_ARENA_INK = (0xE6, 0xED, 0xF3)  # --arena-ink   : основной текст на тёмном
_ARENA_SOFT = (0x8B, 0x98, 0xA9)  # --arena-soft  : вторичный текст
_FRAME = (0x0B, 0x0E, 0x12)  # --frame       : разделительная линия сплита

# — шрифты (DejaVu, см. assets/fonts/LICENSE.md) —
_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
_FONT_MONO = _FONTS_DIR / "DejaVuSansMono.ttf"
_FONT_MONO_BOLD = _FONTS_DIR / "DejaVuSansMono-Bold.ttf"
_FONT_DISPLAY = _FONTS_DIR / "DejaVuSans-Bold.ttf"  # роль Archivo (ник/заголовок)
_FONT_BODY = _FONTS_DIR / "DejaVuSans.ttf"

_MINUS_SIGN = "−"  # типографский минус (как «−18 Elo» в §13)


@dataclass(frozen=True, slots=True)
class PlayerCard:
    """Одна сторона карточки."""

    username: str
    score: int
    delta: int  # дельта Эло, может быть отрицательной


@dataclass(frozen=True, slots=True)
class CardData:
    """Данные результата для рендера.

    ``winner`` — сторона победителя (``"left"``/``"right"``) или ``None`` для ничьей.
    Сторону задаём явным литералом (а не идентичностью объекта), чтобы рендер
    не зависел от того, тем же ли объектом передан победитель.
    """

    topic: str
    left: PlayerCard
    right: PlayerCard
    winner: Literal["left", "right"] | None  # None → ничья


@lru_cache(maxsize=16)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _fmt_delta(delta: int) -> str:
    """Дельта Эло в diff-стиле: ``+24`` / ``−18`` (типографский минус)."""
    if delta < 0:
        return f"{_MINUS_SIGN}{abs(delta)}"
    return f"+{delta}"


def _diagonal_split(
    draw: ImageDraw.ImageDraw, left_color: tuple[int, int, int], right_color: tuple[int, int, int]
) -> None:
    """Заливает фон двумя половинами по наклонной линии ≈78° (VS-сплит §13)."""
    # Наклон: верх линии правее низа — даёт «спортивный» диагональный сплит.
    skew = 150
    top_x = WIDTH // 2 + skew
    bottom_x = WIDTH // 2 - skew
    left_poly = [(0, 0), (top_x, 0), (bottom_x, HEIGHT), (0, HEIGHT)]
    right_poly = [(top_x, 0), (WIDTH, 0), (WIDTH, HEIGHT), (bottom_x, HEIGHT)]
    draw.polygon(left_poly, fill=left_color)
    draw.polygon(right_poly, fill=right_color)
    # Тонкая разделительная линия по стыку.
    draw.line([(top_x, 0), (bottom_x, HEIGHT)], fill=_FRAME, width=6)


def _draw_side(
    draw: ImageDraw.ImageDraw,
    player: PlayerCard,
    *,
    center_x: int,
    is_winner: bool | None,
) -> None:
    """Рисует подпись одной стороны: ник, счёт, дельта Эло."""
    name_font = _font(str(_FONT_DISPLAY), 48)
    score_font = _font(str(_FONT_MONO_BOLD), 132)
    delta_font = _font(str(_FONT_MONO_BOLD), 40)
    label_font = _font(str(_FONT_BODY), 26)

    # Ник (обрезаем длинные, чтобы не вылезать за половину).
    name = player.username if len(player.username) <= 14 else player.username[:13] + "…"
    _centered(draw, name, center_x, 150, name_font, _ARENA_INK)

    # Счёт — моноширинный, крупный.
    _centered(draw, str(player.score), center_x, 250, score_font, _ARENA_INK)

    # Дельта Эло — моноширинный, цвет по знаку.
    delta_color = _PLUS_BRIGHT if player.delta >= 0 else _MINUS_BRIGHT
    _centered(draw, f"{_fmt_delta(player.delta)} Elo", center_x, 420, delta_font, delta_color)

    # Метка исхода.
    if is_winner is None:
        label = "DRAW"
        label_color = _ARENA_SOFT
    elif is_winner:
        label = "WINNER"
        label_color = _PLUS_BRIGHT
    else:
        label = "DEFEAT"
        label_color = _ARENA_SOFT
    _centered(draw, label, center_x, 500, label_font, label_color)


def _centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_x: int,
    top_y: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    draw.text((center_x - width // 2, top_y), text, font=font, fill=color)


def render_card(data: CardData) -> bytes:
    """Чистая функция рендера: :class:`CardData` → bytes PNG 1200×630."""
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)

    is_draw = data.winner is None
    if is_draw:
        _diagonal_split(draw, _SHARE_DRAW_L, _SHARE_DRAW_R)
    else:
        # Зелёная половина — у победителя, красная — у проигравшего.
        left_is_winner = data.winner == "left"
        left_color = _SHARE_PLUS if left_is_winner else _SHARE_MINUS
        right_color = _SHARE_MINUS if left_is_winner else _SHARE_PLUS
        _diagonal_split(draw, left_color, right_color)

    # Заголовок темы (по центру сверху).
    topic_font = _font(str(_FONT_BODY), 30)
    topic_text = data.topic.upper()
    _centered(draw, topic_text, WIDTH // 2, 56, topic_font, _ARENA_SOFT)

    # Стороны.
    if is_draw:
        left_winner: bool | None = None
        right_winner: bool | None = None
    else:
        left_winner = data.winner == "left"
        right_winner = not left_winner
    _draw_side(draw, data.left, center_x=290, is_winner=left_winner)
    _draw_side(draw, data.right, center_x=910, is_winner=right_winner)

    # VS-бейдж по центру.
    vs_font = _font(str(_FONT_DISPLAY), 56)
    _centered(draw, "VS", WIDTH // 2, 280, vs_font, _ARENA_INK)

    # Водяной знак diffduel.com — обязателен (нижний правый угол).
    wm_font = _font(str(_FONT_BODY), 28)
    watermark = "diffduel.com"
    bbox = draw.textbbox((0, 0), watermark, font=wm_font)
    wm_w = bbox[2] - bbox[0]
    draw.text((WIDTH - wm_w - 32, HEIGHT - 52), watermark, font=wm_font, fill=_ARENA_SOFT)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
