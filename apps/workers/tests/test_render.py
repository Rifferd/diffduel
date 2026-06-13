"""Тесты чистого рендера карточки: валидность PNG, размер, три исхода."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from src.workers.render import HEIGHT, WIDTH, CardData, PlayerCard, _fmt_delta, render_card

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _win_loss() -> CardData:
    left = PlayerCard(username="alice", score=4, delta=24)
    right = PlayerCard(username="bob", score=2, delta=-18)
    return CardData(topic="sql", left=left, right=right, winner="left")


def _draw() -> CardData:
    left = PlayerCard(username="alice", score=3, delta=0)
    right = PlayerCard(username="bob", score=3, delta=0)
    return CardData(topic="python", left=left, right=right, winner=None)


def _right_wins() -> CardData:
    left = PlayerCard(username="alice", score=1, delta=-15)
    right = PlayerCard(username="bob", score=5, delta=21)
    return CardData(topic="algorithms", left=left, right=right, winner="right")


@pytest.mark.parametrize("data", [_win_loss(), _draw(), _right_wins()])
def test_render_card_returns_valid_png(data: CardData) -> None:
    png = render_card(data)
    assert png, "PNG не должен быть пустым"
    assert png.startswith(_PNG_SIGNATURE), "должна быть PNG-сигнатура"
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    assert image.size == (WIDTH, HEIGHT) == (1200, 630)


def test_render_long_username_does_not_crash() -> None:
    long_name = "x" * 64
    data = CardData(
        topic="sql",
        left=PlayerCard(username=long_name, score=5, delta=30),
        right=PlayerCard(username="bob", score=0, delta=-30),
        winner="left",
    )
    png = render_card(data)
    assert png.startswith(_PNG_SIGNATURE)


def test_fmt_delta_diff_style() -> None:
    assert _fmt_delta(24) == "+24"
    assert _fmt_delta(0) == "+0"
    assert _fmt_delta(-18) == "−18"  # типографский минус
