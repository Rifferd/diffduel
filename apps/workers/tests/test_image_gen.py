"""Тесты логики воркера: идемпотентность, маппинг, устойчивость к ошибкам."""

from __future__ import annotations

from src.workers.events import DuelFinished
from src.workers.image_gen import ImageGenProcessor, _build_card_data
from src.workers.internal_client import DuelCard

_LEFT = "aaaaaaaa-0000-0000-0000-000000000000"
_RIGHT = "bbbbbbbb-0000-0000-0000-000000000000"


def _event(winner: str | None = _LEFT) -> DuelFinished:
    return DuelFinished(
        duel_id="duel-1",
        topic="sql",
        players=(_LEFT, _RIGHT),
        winner_id=winner,
        deltas={_LEFT: 24, _RIGHT: -18},
        scores={_LEFT: 4, _RIGHT: 2},
    )


class FakeInternal:
    """Мок internal-клиента: фиксирует вызовы set_share_card."""

    def __init__(self, *, existing_key: str | None = None) -> None:
        self._card = DuelCard(
            duel_id="duel-1",
            usernames={_LEFT: "alice", _RIGHT: "bob"},
            share_card_key=existing_key,
        )
        self.set_calls: list[tuple[str, str]] = []
        self.get_calls = 0

    async def get_duel_card(self, duel_id: str) -> DuelCard:
        self.get_calls += 1
        return self._card

    async def set_share_card(self, duel_id: str, key: str) -> None:
        self.set_calls.append((duel_id, key))


class FakeStorage:
    """Мок S3-хранилища: возвращает ключ, считает аплоады."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.uploads: list[str] = []

    @staticmethod
    def key_for(duel_id: str) -> str:
        return f"{duel_id}.png"

    async def upload_card(self, duel_id: str, png: bytes) -> str:
        if self.fail:
            raise RuntimeError("S3 down")
        assert png.startswith(b"\x89PNG")
        self.uploads.append(duel_id)
        return self.key_for(duel_id)


def _processor(internal: object, storage: object, max_attempts: int = 3) -> ImageGenProcessor:
    return ImageGenProcessor(internal=internal, storage=storage, max_attempts=max_attempts)  # type: ignore[arg-type]


async def test_renders_and_records_key() -> None:
    internal = FakeInternal()
    storage = FakeStorage()
    result = await _processor(internal, storage).process_with_retries(_event())
    assert result.status == "rendered"
    assert result.key == "duel-1.png"
    assert storage.uploads == ["duel-1"]
    assert internal.set_calls == [("duel-1", "duel-1.png")]


async def test_idempotent_skip_when_key_exists() -> None:
    internal = FakeInternal(existing_key="duel-1.png")
    storage = FakeStorage()
    result = await _processor(internal, storage).process_with_retries(_event())
    assert result.status == "skipped"
    assert result.key == "duel-1.png"
    assert storage.uploads == []  # рендер не запускался
    assert internal.set_calls == []  # ключ не перезаписывался


async def test_poison_message_gives_up_after_max_attempts() -> None:
    internal = FakeInternal()
    storage = FakeStorage(fail=True)
    result = await _processor(internal, storage, max_attempts=2).process_with_retries(_event())
    assert result.status == "failed"
    assert result.key is None
    assert internal.set_calls == []


def test_build_card_data_draw() -> None:
    data = _build_card_data(_event(winner=None), {_LEFT: "alice", _RIGHT: "bob"})
    assert data.winner is None  # ничья
    assert data.left.username == "alice"
    assert data.right.delta == -18


def test_build_card_data_right_winner() -> None:
    data = _build_card_data(_event(winner=_RIGHT), {_LEFT: "alice", _RIGHT: "bob"})
    assert data.winner == "right"


def test_build_card_data_falls_back_to_short_id() -> None:
    data = _build_card_data(_event(), usernames={})
    assert data.left.username == _LEFT[:8]
