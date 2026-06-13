"""Парс конверта Kafka-события ``duels.finished``.

Конверт (conventions.md):
``{"v": 1, "type": "...", "occurred_at": iso8601, "payload": {...}}``.

payload (duels.md / apps/api/src/duels/service.py::_emit_finished):
``{duel_id, topic, players, winner_id, deltas, scores}`` — все id строками.

Парс ручной и строгий: битый конверт даёт ``EnvelopeError`` (мы его логируем
и коммитим offset — повторять разбор мусора смысла нет, см. consumer).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class EnvelopeError(ValueError):
    """Конверт/payload события не соответствует контракту."""


@dataclass(frozen=True, slots=True)
class DuelFinished:
    """Полезная нагрузка события ``duels.finished``."""

    duel_id: str
    topic: str
    players: tuple[str, str]
    winner_id: str | None
    deltas: dict[str, int]
    scores: dict[str, int]


def _require(mapping: object, key: str) -> object:
    if not isinstance(mapping, dict):
        raise EnvelopeError(f"ожидался объект, получено {type(mapping).__name__}")
    if key not in mapping:
        raise EnvelopeError(f"отсутствует поле {key!r}")
    return mapping[key]


def _as_str(value: object, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnvelopeError(f"поле {key!r} должно быть непустой строкой")
    return value


def _as_int_map(value: object, key: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise EnvelopeError(f"поле {key!r} должно быть объектом")
    result: dict[str, int] = {}
    for k, v in value.items():
        if not isinstance(k, str):
            raise EnvelopeError(f"ключи {key!r} должны быть строками")
        if isinstance(v, bool) or not isinstance(v, int):
            raise EnvelopeError(f"значения {key!r} должны быть целыми")
        result[k] = v
    return result


def parse_envelope(raw: bytes | str) -> DuelFinished:
    """Разбирает сырое сообщение топика в :class:`DuelFinished`.

    Бросает :class:`EnvelopeError` на любой структурной ошибке.
    """
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EnvelopeError(f"невалидный JSON: {exc}") from exc

    if not isinstance(envelope, dict):
        raise EnvelopeError("конверт должен быть JSON-объектом")

    event_type = _as_str(_require(envelope, "type"), "type")
    if event_type != "duels.finished":
        raise EnvelopeError(f"неожиданный type: {event_type!r}")
    # Версия — контролируем, но не падаем на будущих минорных (только наличие).
    _require(envelope, "v")

    payload = _require(envelope, "payload")
    duel_id = _as_str(_require(payload, "duel_id"), "duel_id")
    topic = _as_str(_require(payload, "topic"), "topic")

    raw_players = _require(payload, "players")
    if not isinstance(raw_players, list) or len(raw_players) != 2:
        raise EnvelopeError("players должен быть списком из двух id")
    players = (_as_str(raw_players[0], "players[0]"), _as_str(raw_players[1], "players[1]"))

    raw_winner = payload.get("winner_id") if isinstance(payload, dict) else None
    winner_id: str | None
    if raw_winner is None:
        winner_id = None
    else:
        winner_id = _as_str(raw_winner, "winner_id")
        if winner_id not in players:
            raise EnvelopeError("winner_id не входит в players")

    deltas = _as_int_map(_require(payload, "deltas"), "deltas")
    scores = _as_int_map(_require(payload, "scores"), "scores")

    return DuelFinished(
        duel_id=duel_id,
        topic=topic,
        players=players,
        winner_id=winner_id,
        deltas=deltas,
        scores=scores,
    )
