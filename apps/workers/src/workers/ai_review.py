"""Воркер ai-review: ``ai.review.requested`` → Claude → запись результата в API.

Содержит:
- :func:`build_prompt` — чистая (от Kafka/SDK) сборка system+user промпта из
  данных дуэли; отдельно тестируется на фикстуре;
- :class:`ClaudeReviewer` — обёртка над официальным Anthropic SDK (стриминг,
  adaptive thinking, обработка ``stop_reason == "refusal"``);
- :class:`AiReviewProcessor` — логика обработки одного события с идемпотентностью
  по (duel_id, user_id) (запись уже done → пропуск);
- :class:`AiReviewConsumer` — aiokafka-раннер (at-least-once, ручной коммит);
- ``main()`` / ``python -m src.workers.ai_review`` — entrypoint.

Флаг: если ANTHROPIC_API_KEY пуст → пишем failed «AI-разбор временно недоступен»
(чтобы UI не висел в pending). Любая ошибка/таймаут SDK → status=failed.
"""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from src.workers.config import Settings, get_settings
from src.workers.events import AiReviewRequested, EnvelopeError, parse_ai_review_envelope
from src.workers.internal_client import InternalClient, ReviewData
from src.workers.logging import configure_logging, get_logger
from src.workers.telemetry import KafkaHeaders, consume_span, init_telemetry

logger = get_logger("ai_review")

_KEY_MISSING_ERROR = "AI-разбор временно недоступен"

_SYSTEM_PROMPT = (
    "Ты — тренер по программированию. Разбери ошибки игрока в дуэли по-русски, "
    "кратко и по делу, с конкретными советами по каждой проваленной задаче. "
    "Не пересказывай условие целиком; объясни, почему верный ответ верный, и что "
    "стоит подтянуть. Если все задачи решены верно — коротко похвали и предложи "
    "следующий шаг для роста."
)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Итог разбора (готов к записи через internal API)."""

    status: str  # "done" | "failed"
    content: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Итог обработки одного события (для логов/тестов)."""

    duel_id: str
    user_id: str
    status: str  # "done" | "failed" | "skipped"


def build_prompt(data: ReviewData) -> tuple[str, str]:
    """Чистая сборка (system, user) промпта из данных дуэли.

    Текст user перечисляет задачи: вопрос, варианты, верный ответ, объяснение,
    что выбрал игрок и время. Эталоны берутся из internal-данных.
    """
    lines: list[str] = [
        f"Тема дуэли: {data.topic or 'не указана'}.",
        f"Всего задач: {len(data.tasks)}.",
        "",
        "Разбор по задачам:",
    ]
    for i, task in enumerate(data.tasks, start=1):
        question = _as_text(task.body.get("question")) or "(без текста вопроса)"
        lines.append(f"\nЗадача {i}: {question}")

        options = task.body.get("options")
        correct_idx = task.answer.get("correct")
        if isinstance(options, list):
            for j, opt in enumerate(options):
                mark = " (верный)" if isinstance(correct_idx, int) and j == correct_idx else ""
                lines.append(f"  {j}. {_as_text(opt)}{mark}")

        if task.is_correct:
            verdict = "игрок ответил ВЕРНО"
        elif task.selected is None:
            verdict = "игрок НЕ ответил (или ошибся)"
        else:
            verdict = f"игрок выбрал вариант {task.selected} — НЕВЕРНО"
        time_part = f", время {task.time_ms} мс" if task.time_ms is not None else ""
        lines.append(f"  Результат: {verdict}{time_part}.")

        if task.explanation:
            lines.append(f"  Пояснение к задаче: {task.explanation}")

    lines.append(
        "\nДай разбор: сначала общий итог, затем по каждой проваленной задаче — "
        "что пошло не так и как это запомнить."
    )
    return _SYSTEM_PROMPT, "\n".join(lines)


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


class ClaudeReviewer:
    """Обёртка над Anthropic SDK. Пустой ключ → не вызываем сеть, отдаём failed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def review(self, data: ReviewData) -> ReviewResult:
        if not self._settings.anthropic_api_key:
            logger.warning("ai_review_no_api_key", duel_id=data.duel_id)
            return ReviewResult(status="failed", error=_KEY_MISSING_ERROR)

        system, user = build_prompt(data)
        try:
            text = await asyncio.to_thread(self._call_claude, system, user)
        except _RefusalError:
            logger.warning("ai_review_refused", duel_id=data.duel_id, user_id=data.user_id)
            return ReviewResult(
                status="failed",
                error="Не удалось сгенерировать разбор: запрос отклонён моделью.",
            )
        except Exception as exc:  # noqa: BLE001 — любая ошибка SDK → failed
            logger.warning("ai_review_sdk_error", duel_id=data.duel_id, error=str(exc))
            return ReviewResult(status="failed", error=_KEY_MISSING_ERROR)

        if not text.strip():
            return ReviewResult(status="failed", error=_KEY_MISSING_ERROR)
        return ReviewResult(status="done", content=text)

    def _call_claude(self, system: str, user: str) -> str:
        """Синхронный вызов SDK (запускается через asyncio.to_thread).

        Стриминг (потенциально длинный вывод), adaptive thinking, без
        temperature/top_p. Обработка refusal ДО чтения content.
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        with client.messages.stream(
            model=self._settings.ai_review_model,
            max_tokens=self._settings.ai_review_max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            raise _RefusalError

        parts: list[str] = []
        for block in message.content:
            if block.type == "text":
                parts.append(block.text)
        return "".join(parts)


class _RefusalError(Exception):
    """Маркер: модель отказалась (stop_reason == 'refusal')."""


class AiReviewProcessor:
    """Логика обработки одного ``ai.review.requested`` (без Kafka)."""

    def __init__(self, *, internal: InternalClient, reviewer: ClaudeReviewer) -> None:
        self._internal = internal
        self._reviewer = reviewer

    async def process(self, event: AiReviewRequested) -> ProcessResult:
        """Идемпотентно генерирует разбор. Возвращает результат; не бросает."""
        duel_id, user_id = event.duel_id, event.user_id
        try:
            data = await self._internal.get_review_data(duel_id, user_id)
            result = await self._reviewer.review(data)
            await self._internal.write_ai_review(
                duel_id,
                user_id,
                status=result.status,
                content=result.content,
                error=result.error,
            )
            logger.info(
                "ai_review_processed", duel_id=duel_id, user_id=user_id, status=result.status
            )
            return ProcessResult(duel_id, user_id, result.status)
        except Exception as exc:  # noqa: BLE001 — обработчик не должен ронять консьюмер
            logger.warning(
                "ai_review_attempt_failed", duel_id=duel_id, user_id=user_id, error=str(exc)
            )
            raise

    async def process_with_retries(
        self, event: AiReviewRequested, *, max_attempts: int
    ) -> ProcessResult:
        """Обработка с ретраями. После ``max_attempts`` — failed-запись best-effort."""
        attempts = max(1, max_attempts)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self.process(event)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < attempts:
                    await asyncio.sleep(0.2 * attempt)
        logger.error(
            "ai_review_failed_giving_up",
            duel_id=event.duel_id,
            user_id=event.user_id,
            attempts=attempts,
            error=str(last_exc),
        )
        try:
            await self._internal.write_ai_review(
                event.duel_id, event.user_id, status="failed", error=_KEY_MISSING_ERROR
            )
        except Exception:  # noqa: BLE001 — API недоступен; offset всё равно коммитим
            logger.warning("ai_review_failed_write_failed", duel_id=event.duel_id)
        return ProcessResult(event.duel_id, event.user_id, "failed")


class AiReviewConsumer:
    """aiokafka-раннер: consume ``ai.review.requested``, at-least-once, ручной коммит."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def _start_consumer(self) -> AIOKafkaConsumer:
        backoff = self._settings.broker_connect_backoff_s
        while not self._stop.is_set():
            consumer = AIOKafkaConsumer(
                self._settings.ai_review_topic,
                bootstrap_servers=self._settings.kafka_brokers,
                group_id=self._settings.ai_review_group_id,
                enable_auto_commit=False,  # ручной коммит → at-least-once
                auto_offset_reset="earliest",
            )
            try:
                await consumer.start()
                logger.info(
                    "consumer_started",
                    topic=self._settings.ai_review_topic,
                    group_id=self._settings.ai_review_group_id,
                )
                return consumer
            except KafkaConnectionError as exc:
                await consumer.stop()
                logger.warning("broker_unavailable_retry", error=str(exc), backoff_s=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.broker_connect_backoff_max_s)
        raise asyncio.CancelledError

    async def run(self) -> None:
        consumer = await self._start_consumer()
        async with InternalClient(self._settings) as internal:
            reviewer = ClaudeReviewer(self._settings)
            processor = AiReviewProcessor(internal=internal, reviewer=reviewer)
            try:
                while not self._stop.is_set():
                    batches = await consumer.getmany(timeout_ms=1000, max_records=10)
                    for _tp, messages in batches.items():
                        for message in messages:
                            await self._handle(processor, message.value, message.headers)
                    if batches:
                        await consumer.commit()
            finally:
                await consumer.stop()
                logger.info("consumer_stopped")

    async def _handle(
        self,
        processor: AiReviewProcessor,
        raw: bytes | None,
        headers: KafkaHeaders | None = None,
    ) -> None:
        if raw is None:
            logger.warning("empty_message_skipped")
            return
        try:
            event = parse_ai_review_envelope(raw)
        except EnvelopeError as exc:
            logger.error("envelope_parse_failed", error=str(exc))
            return
        with consume_span("ai_review.process", headers):
            await processor.process_with_retries(
                event, max_attempts=self._settings.process_max_attempts
            )


async def _amain() -> None:
    configure_logging()
    settings = get_settings()
    init_telemetry(settings)
    consumer = AiReviewConsumer(settings)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, consumer.request_stop)

    logger.info("ai_review_starting", brokers=settings.kafka_brokers)
    await consumer.run()


def main() -> None:
    """Entrypoint: ``python -m src.workers.ai_review``."""
    try:
        asyncio.run(_amain())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
