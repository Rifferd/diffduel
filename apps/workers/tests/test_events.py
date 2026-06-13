"""Тесты парса конверта duels.finished: валидный и битые случаи."""

from __future__ import annotations

import json

import pytest

from src.workers.events import EnvelopeError, parse_envelope


def _valid_payload() -> dict[str, object]:
    return {
        "duel_id": "11111111-1111-1111-1111-111111111111",
        "topic": "22222222-2222-2222-2222-222222222222",
        "players": [
            "aaaaaaaa-0000-0000-0000-000000000000",
            "bbbbbbbb-0000-0000-0000-000000000000",
        ],
        "winner_id": "aaaaaaaa-0000-0000-0000-000000000000",
        "deltas": {
            "aaaaaaaa-0000-0000-0000-000000000000": 24,
            "bbbbbbbb-0000-0000-0000-000000000000": -18,
        },
        "scores": {
            "aaaaaaaa-0000-0000-0000-000000000000": 4,
            "bbbbbbbb-0000-0000-0000-000000000000": 2,
        },
    }


def _envelope(payload: dict[str, object]) -> bytes:
    envelope = {
        "v": 1,
        "type": "duels.finished",
        "occurred_at": "2026-06-12T00:00:00Z",
        "payload": payload,
    }
    return json.dumps(envelope).encode()


def test_parse_valid_envelope() -> None:
    event = parse_envelope(_envelope(_valid_payload()))
    assert event.duel_id == "11111111-1111-1111-1111-111111111111"
    assert event.players[0] == "aaaaaaaa-0000-0000-0000-000000000000"
    assert event.winner_id == "aaaaaaaa-0000-0000-0000-000000000000"
    assert event.deltas["bbbbbbbb-0000-0000-0000-000000000000"] == -18
    assert event.scores["aaaaaaaa-0000-0000-0000-000000000000"] == 4


def test_parse_draw_winner_none() -> None:
    payload = _valid_payload()
    payload["winner_id"] = None
    event = parse_envelope(_envelope(payload))
    assert event.winner_id is None


def test_parse_invalid_json() -> None:
    with pytest.raises(EnvelopeError):
        parse_envelope(b"{not json")


def test_parse_wrong_type() -> None:
    raw = json.dumps(
        {"v": 1, "type": "answers.submitted", "occurred_at": "x", "payload": _valid_payload()}
    ).encode()
    with pytest.raises(EnvelopeError):
        parse_envelope(raw)


def test_parse_missing_payload_field() -> None:
    payload = _valid_payload()
    del payload["scores"]
    with pytest.raises(EnvelopeError):
        parse_envelope(_envelope(payload))


def test_parse_winner_not_in_players() -> None:
    payload = _valid_payload()
    payload["winner_id"] = "cccccccc-0000-0000-0000-000000000000"
    with pytest.raises(EnvelopeError):
        parse_envelope(_envelope(payload))


def test_parse_players_wrong_length() -> None:
    payload = _valid_payload()
    payload["players"] = ["only-one"]
    with pytest.raises(EnvelopeError):
        parse_envelope(_envelope(payload))


def test_parse_bool_not_accepted_as_int() -> None:
    payload = _valid_payload()
    payload["scores"] = {"aaaaaaaa-0000-0000-0000-000000000000": True}
    with pytest.raises(EnvelopeError):
        parse_envelope(_envelope(payload))
