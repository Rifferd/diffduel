"""Тесты ai-review воркера: сборка промпта, refusal, пустой ключ, идемпотентность.

Anthropic SDK ЗАМОКАН — реальных сетевых вызовов нет.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import pytest

from src.workers.ai_review import (
    AiReviewProcessor,
    ClaudeReviewer,
    build_prompt,
)
from src.workers.config import Settings
from src.workers.events import AiReviewRequested, EnvelopeError, parse_ai_review_envelope
from src.workers.internal_client import ReviewData, ReviewTask

_DUEL = "11111111-0000-0000-0000-000000000000"
_USER = "22222222-0000-0000-0000-000000000000"


def _review_data() -> ReviewData:
    return ReviewData(
        duel_id=_DUEL,
        user_id=_USER,
        topic="sql",
        tasks=[
            ReviewTask(
                task_id="t1",
                body={
                    "question": "Чем INNER JOIN отличается от LEFT JOIN?",
                    "options": ["верный вариант", "неверный", "ещё неверный"],
                },
                answer={"correct": 0},
                explanation="INNER JOIN оставляет только совпавшие строки.",
                selected=0,
                is_correct=True,
                time_ms=1200,
            ),
            ReviewTask(
                task_id="t2",
                body={
                    "question": "Что вернёт NULL = NULL?",
                    "options": ["TRUE", "NULL", "FALSE"],
                },
                answer={"correct": 1},
                explanation="Сравнение с NULL даёт NULL, а не TRUE.",
                selected=0,
                is_correct=False,
                time_ms=3000,
            ),
        ],
    )


def _settings(*, api_key: str = "") -> Settings:
    return Settings(app_env="test", anthropic_api_key=api_key)


# --- парс конверта события ---------------------------------------------------


def test_parse_ai_review_envelope() -> None:
    raw = json.dumps(
        {
            "v": 1,
            "type": "ai.review.requested",
            "occurred_at": "2026-06-14T00:00:00+00:00",
            "payload": {"duel_id": _DUEL, "user_id": _USER},
        }
    )
    event = parse_ai_review_envelope(raw)
    assert event == AiReviewRequested(duel_id=_DUEL, user_id=_USER)


def test_parse_ai_review_envelope_wrong_type() -> None:
    raw = json.dumps({"v": 1, "type": "duels.finished", "payload": {}})
    with pytest.raises(EnvelopeError):
        parse_ai_review_envelope(raw)


# --- чистая сборка промпта ---------------------------------------------------


def test_build_prompt_from_fixture() -> None:
    system, user = build_prompt(_review_data())
    assert "тренер по программированию" in system
    # Тема и счёт задач.
    assert "Тема дуэли: sql" in user
    assert "Всего задач: 2" in user
    # Вопросы и эталоны попадают в промпт.
    assert "INNER JOIN" in user
    assert "(верный)" in user  # помечен верный вариант
    # Вердикты игрока: верно / неверно.
    assert "ВЕРНО" in user
    assert "игрок выбрал вариант 0 — НЕВЕРНО" in user
    # Пояснения задач включены.
    assert "Сравнение с NULL" in user
    # Время ответов.
    assert "1200 мс" in user


def test_build_prompt_no_answer() -> None:
    data = ReviewData(
        duel_id=_DUEL,
        user_id=_USER,
        topic="python",
        tasks=[
            ReviewTask(
                task_id="t1",
                body={"question": "Q?", "options": ["a", "b"]},
                answer={"correct": 1},
                explanation=None,
                selected=None,
                is_correct=False,
                time_ms=None,
            )
        ],
    )
    _system, user = build_prompt(data)
    assert "НЕ ответил" in user
    # Нет времени — без хвоста про мс.
    assert "мс" not in user


# --- мок Anthropic SDK -------------------------------------------------------


class _FakeBlock:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class _FakeMessage:
    def __init__(self, *, stop_reason: str, content: list[_FakeBlock]) -> None:
        self.stop_reason = stop_reason
        self.content = content


class _FakeStream:
    def __init__(self, message: _FakeMessage) -> None:
        self._message = message

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def get_final_message(self) -> _FakeMessage:
        return self._message


class _FakeMessages:
    def __init__(self, message: _FakeMessage, calls: list[dict[str, Any]]) -> None:
        self._message = message
        self._calls = calls

    def stream(self, **kwargs: Any) -> _FakeStream:
        self._calls.append(kwargs)
        return _FakeStream(self._message)


class _FakeAnthropic:
    """Подменяет anthropic.Anthropic — без сети."""

    last_message: _FakeMessage
    calls: list[dict[str, Any]] = []

    def __init__(self, *, api_key: str) -> None:
        self.messages = _FakeMessages(_FakeAnthropic.last_message, _FakeAnthropic.calls)


@pytest.fixture
def _mock_anthropic(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAnthropic]:
    """Подкладывает фейковый модуль ``anthropic`` в sys.modules."""
    _FakeAnthropic.calls = []
    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _FakeAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return _FakeAnthropic


# --- ClaudeReviewer ----------------------------------------------------------


async def test_review_empty_key_returns_failed() -> None:
    """Пустой ANTHROPIC_API_KEY → failed без вызова сети."""
    reviewer = ClaudeReviewer(_settings(api_key=""))
    result = await reviewer.review(_review_data())
    assert result.status == "failed"
    assert result.error == "AI-разбор временно недоступен"
    assert result.content is None


async def test_review_done_extracts_text(_mock_anthropic: type[_FakeAnthropic]) -> None:
    _mock_anthropic.last_message = _FakeMessage(
        stop_reason="end_turn",
        content=[_FakeBlock("thinking", "..."), _FakeBlock("text", "Разбор: подтяни NULL.")],
    )
    reviewer = ClaudeReviewer(_settings(api_key="sk-test"))
    result = await reviewer.review(_review_data())
    assert result.status == "done"
    assert result.content == "Разбор: подтяни NULL."
    # Параметры вызова: модель, adaptive thinking, без temperature/top_p.
    call = _mock_anthropic.calls[-1]
    assert call["model"] == "claude-opus-4-8"
    assert call["thinking"] == {"type": "adaptive"}
    assert "temperature" not in call
    assert "top_p" not in call


async def test_review_refusal_returns_failed(_mock_anthropic: type[_FakeAnthropic]) -> None:
    _mock_anthropic.last_message = _FakeMessage(
        stop_reason="refusal",
        content=[_FakeBlock("text", "не должно читаться")],
    )
    reviewer = ClaudeReviewer(_settings(api_key="sk-test"))
    result = await reviewer.review(_review_data())
    assert result.status == "failed"
    assert result.error is not None
    assert "отклонён" in result.error
    # content при refusal не читается.
    assert result.content is None


# --- AiReviewProcessor (идемпотентность + запись) ----------------------------


class _FakeInternal:
    def __init__(self, data: ReviewData) -> None:
        self._data = data
        self.writes: list[dict[str, Any]] = []

    async def get_review_data(self, duel_id: str, user_id: str) -> ReviewData:
        return self._data

    async def write_ai_review(
        self,
        duel_id: str,
        user_id: str,
        *,
        status: str,
        content: str | None = None,
        error: str | None = None,
    ) -> None:
        self.writes.append(
            {
                "duel_id": duel_id,
                "user_id": user_id,
                "status": status,
                "content": content,
                "error": error,
            }
        )


class _FakeReviewer:
    def __init__(self, result: Any) -> None:
        self._result = result

    async def review(self, data: ReviewData) -> Any:
        return self._result


async def test_processor_writes_done() -> None:
    from src.workers.ai_review import ReviewResult

    internal = _FakeInternal(_review_data())
    reviewer = _FakeReviewer(ReviewResult(status="done", content="ОК"))
    proc = AiReviewProcessor(internal=internal, reviewer=reviewer)  # type: ignore[arg-type]
    result = await proc.process(AiReviewRequested(duel_id=_DUEL, user_id=_USER))
    assert result.status == "done"
    assert internal.writes == [
        {"duel_id": _DUEL, "user_id": _USER, "status": "done", "content": "ОК", "error": None}
    ]


async def test_processor_retries_then_failed() -> None:
    class _BoomInternal(_FakeInternal):
        async def get_review_data(self, duel_id: str, user_id: str) -> ReviewData:
            raise RuntimeError("internal down")

    internal = _BoomInternal(_review_data())
    reviewer = _FakeReviewer(None)
    proc = AiReviewProcessor(internal=internal, reviewer=reviewer)  # type: ignore[arg-type]
    result = await proc.process_with_retries(
        AiReviewRequested(duel_id=_DUEL, user_id=_USER), max_attempts=2
    )
    # После исчерпания попыток — best-effort failed-запись.
    assert result.status == "failed"
    assert internal.writes[-1]["status"] == "failed"
    assert internal.writes[-1]["error"] == "AI-разбор временно недоступен"
