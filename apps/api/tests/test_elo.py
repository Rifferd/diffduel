"""Unit-тесты чистого Эло-модуля (без БД)."""

from __future__ import annotations

from src.duels import elo


def test_expected_symmetry_equal_ratings() -> None:
    # Равные рейтинги → ожидание 0.5 у обоих.
    assert elo.expected(1200, 1200) == 0.5


def test_expected_monotonic() -> None:
    # Более высокий рейтинг → ожидание ближе к 1.
    assert elo.expected(1600, 1200) > 0.5
    assert elo.expected(1200, 1600) < 0.5


def test_zero_sum_for_equal_ratings() -> None:
    # При равных рейтингах дельты строго симметричны (сумма = 0).
    win = elo.compute(1200, 1200, 1.0)
    assert win.delta_a == 16
    assert win.delta_b == -16
    assert win.delta_a + win.delta_b == 0

    draw = elo.compute(1200, 1200, 0.5)
    assert draw.delta_a == 0
    assert draw.delta_b == 0


def test_draw_unequal_ratings_directions() -> None:
    # Ничья при разном рейтинге: фаворит теряет, аутсайдер набирает.
    out = elo.compute(1400, 1200, 0.5)
    assert out.delta_a < 0
    assert out.delta_b > 0


def test_symmetry_within_one_for_unequal() -> None:
    # Из-за независимого round() допускается асимметрия ±1 — это ок.
    out = elo.compute(1400, 1200, 1.0)
    assert abs(out.delta_a + out.delta_b) <= 1


def test_new_elo_applies_delta() -> None:
    out = elo.compute(1200, 1187, 1.0)
    assert out.new_elo_a == 1200 + out.delta_a
    assert out.new_elo_b == 1187 + out.delta_b


def test_no_clamp_can_go_below_floor() -> None:
    # Клампов нет: проигрыш слабого фавориту уводит рейтинг как есть.
    out = elo.compute(100, 100, 0.0)
    assert out.new_elo_a == 100 - 16
    assert out.delta_a == -16
