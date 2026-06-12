"""Проверка ответов с диспетчеризацией по типу задачи.

Расширяемо под code_bug / sql / design — пока реализован только quiz.
Чекеры чистые: на вход эталон (tasks.answer) и пользовательский ответ,
на выход — вердикт и индекс верной опции (для фидбека фронту).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.core.enums import TaskType
from src.core.errors import ValidationError


@dataclass(slots=True, frozen=True)
class CheckResult:
    """Вердикт проверки."""

    correct: bool
    # Индекс верной опции — отдаётся пользователю после ответа (для фидбека).
    correct_option: int


def _check_quiz(answer: dict[str, object], submitted: dict[str, object]) -> CheckResult:
    """quiz: эталон {"correct": int}, ответ {"selected": int}."""
    correct_option = answer.get("correct")
    if not isinstance(correct_option, int) or isinstance(correct_option, bool):
        # Битый эталон — это ошибка контента, а не пользователя.
        raise ValidationError("Некорректный эталон quiz-задачи", code="invalid_task_answer")
    selected = submitted.get("selected")
    if not isinstance(selected, int) or isinstance(selected, bool):
        raise ValidationError("Ожидается selected: int", code="invalid_answer")
    return CheckResult(correct=selected == correct_option, correct_option=correct_option)


_CHECKERS: dict[TaskType, Callable[[dict[str, object], dict[str, object]], CheckResult]] = {
    TaskType.quiz: _check_quiz,
}


def check_answer(
    task_type: TaskType,
    answer: dict[str, object],
    submitted: dict[str, object],
) -> CheckResult:
    """Диспетчеризация проверки по типу задачи."""
    checker = _CHECKERS.get(task_type)
    if checker is None:
        raise ValidationError(
            f"Проверка задач типа {task_type} пока не поддерживается",
            code="unsupported_task_type",
        )
    return checker(answer, submitted)
