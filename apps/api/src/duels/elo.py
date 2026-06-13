"""Чистые функции рейтинга Эло (спека duels.md, ТЗ §6).

K=32, базовый рейтинг 1200 (per-topic). Никаких клампов: рейтинг может
уходить как угодно вверх/вниз — продуктовое решение MVP.

ВАЖНО про симметрию: при равных рейтингах сумма дельт строго ноль
(delta_a == -delta_b). При неравных рейтингах из-за независимого round()
каждой стороны допускается асимметрия ±1 (например delta_a=+24, delta_b=-25)
— это ожидаемо и приемлемо для MVP.
"""

from __future__ import annotations

from dataclasses import dataclass

K_FACTOR = 32
BASE_RATING = 1200


@dataclass(slots=True, frozen=True)
class EloOutcome:
    """Результат пересчёта Эло для пары игроков."""

    delta_a: int
    delta_b: int
    new_elo_a: int
    new_elo_b: int


def expected(elo_self: int, elo_other: int) -> float:
    """Ожидаемый счёт игрока против соперника: 1/(1+10^((other-self)/400))."""
    return float(1.0 / (1.0 + 10.0 ** ((elo_other - elo_self) / 400.0)))


def _delta(elo_self: int, elo_other: int, score: float) -> int:
    """Дельта рейтинга одной стороны: round(K*(score-expected)).

    round() — банковское округление Python; для .5 даёт ближайшее чётное.
    Спека допускает обычный round(), асимметрия ±1 задокументирована в модуле.
    """
    return round(K_FACTOR * (score - expected(elo_self, elo_other)))


def compute(elo_a: int, elo_b: int, score_a: float) -> EloOutcome:
    """Пересчёт Эло обоих игроков по счёту A (1 победа, 0.5 ничья, 0 поражение)."""
    score_b = 1.0 - score_a
    delta_a = _delta(elo_a, elo_b, score_a)
    delta_b = _delta(elo_b, elo_a, score_b)
    return EloOutcome(
        delta_a=delta_a,
        delta_b=delta_b,
        new_elo_a=elo_a + delta_a,
        new_elo_b=elo_b + delta_b,
    )
