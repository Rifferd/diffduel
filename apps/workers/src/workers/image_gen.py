"""Воркер image-gen: ``duels.finished`` → render → MinIO → запись ключа в API.

Содержит:
- :class:`ImageGenProcessor` — чистая (от Kafka) логика обработки одного события
  с идемпотентностью по share_card_key; легко мокается в тестах;
- :class:`ImageGenConsumer` — aiokafka-раннер (at-least-once, ручной коммит);
- ``main()`` / ``python -m src.workers.image_gen`` — entrypoint.

Устойчивость:
- ошибка рендера/аплоада одного события не роняет консьюмер: до ``process_max_attempts``
  ретраев внутри обработки, после — лог error и offset коммитится (пропуск ядовитого
  сообщения, чтобы не зависнуть навечно);
- offset коммитится только ПОСЛЕ успешной обработки/пропуска (at-least-once);
- брокер недоступен на старте — переподключение с экспоненциальным бэкоффом.
"""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass
from typing import Literal

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from src.workers.config import Settings, get_settings
from src.workers.events import DuelFinished, EnvelopeError, parse_envelope
from src.workers.internal_client import InternalClient
from src.workers.logging import configure_logging, get_logger
from src.workers.render import CardData, PlayerCard, render_card
from src.workers.storage import CardStorage
from src.workers.telemetry import KafkaHeaders, consume_span, init_telemetry, measure_render

logger = get_logger("image_gen")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Итог обработки одного события (для логов/тестов)."""

    duel_id: str
    status: str  # "rendered" | "skipped" | "failed"
    key: str | None = None


class ImageGenProcessor:
    """Логика обработки одного ``duels.finished`` (без Kafka)."""

    def __init__(
        self,
        *,
        internal: InternalClient,
        storage: CardStorage,
        max_attempts: int,
    ) -> None:
        self._internal = internal
        self._storage = storage
        self._max_attempts = max(1, max_attempts)

    async def process(self, event: DuelFinished) -> ProcessResult:
        """Идемпотентно генерирует карточку. Возвращает результат; не бросает."""
        duel_id = event.duel_id
        try:
            # 1. Идемпотентность: если ключ уже есть — пропускаем.
            card = await self._internal.get_duel_card(duel_id)
            if card.share_card_key:
                logger.info("share_card_skip_exists", duel_id=duel_id, key=card.share_card_key)
                return ProcessResult(duel_id, "skipped", card.share_card_key)

            with measure_render():
                png = render_card(_build_card_data(event, card.usernames))
            key = await self._storage.upload_card(duel_id, png)
            await self._internal.set_share_card(duel_id, key)
            logger.info("share_card_done", duel_id=duel_id, key=key)
            return ProcessResult(duel_id, "rendered", key)
        except Exception as exc:  # noqa: BLE001 — обработчик не должен ронять консьюмер
            logger.warning("share_card_attempt_failed", duel_id=duel_id, error=str(exc))
            raise

    async def process_with_retries(self, event: DuelFinished) -> ProcessResult:
        """Обработка с ретраями. После ``max_attempts`` — лог error и status=failed."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self.process(event)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self._max_attempts:
                    await asyncio.sleep(0.2 * attempt)
        logger.error(
            "share_card_failed_giving_up",
            duel_id=event.duel_id,
            attempts=self._max_attempts,
            error=str(last_exc),
        )
        return ProcessResult(event.duel_id, "failed")


def _build_card_data(event: DuelFinished, usernames: dict[str, str]) -> CardData:
    """Маппит payload + имена игроков в :class:`CardData` для рендера."""
    left_id, right_id = event.players

    def side(player_id: str) -> PlayerCard:
        return PlayerCard(
            username=usernames.get(player_id, _short_id(player_id)),
            score=event.scores.get(player_id, 0),
            delta=event.deltas.get(player_id, 0),
        )

    left = side(left_id)
    right = side(right_id)
    winner: Literal["left", "right"] | None
    if event.winner_id is None:
        winner = None
    elif event.winner_id == left_id:
        winner = "left"
    else:
        winner = "right"
    return CardData(topic=event.topic, left=left, right=right, winner=winner)


def _short_id(player_id: str) -> str:
    """Запасная подпись, если имя игрока недоступно (первые 8 символов id)."""
    return player_id[:8]


class ImageGenConsumer:
    """aiokafka-раннер: consume ``duels.finished``, at-least-once, ручной коммит."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def _start_consumer(self) -> AIOKafkaConsumer:
        """Создаёт и подключает консьюмер с бэкоффом, пока брокер не поднимется."""
        backoff = self._settings.broker_connect_backoff_s
        while not self._stop.is_set():
            consumer = AIOKafkaConsumer(
                self._settings.kafka_topic,
                bootstrap_servers=self._settings.kafka_brokers,
                group_id=self._settings.kafka_group_id,
                enable_auto_commit=False,  # ручной коммит → at-least-once
                auto_offset_reset="earliest",
            )
            try:
                await consumer.start()
                logger.info(
                    "consumer_started",
                    topic=self._settings.kafka_topic,
                    group_id=self._settings.kafka_group_id,
                )
                return consumer
            except KafkaConnectionError as exc:
                await consumer.stop()
                logger.warning("broker_unavailable_retry", error=str(exc), backoff_s=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.broker_connect_backoff_max_s)
        raise asyncio.CancelledError

    async def run(self) -> None:
        """Главный цикл консьюмера. Завершается по ``request_stop()``."""
        consumer = await self._start_consumer()
        async with InternalClient(self._settings) as internal:
            storage = CardStorage(self._settings)
            processor = ImageGenProcessor(
                internal=internal,
                storage=storage,
                max_attempts=self._settings.process_max_attempts,
            )
            try:
                while not self._stop.is_set():
                    batches = await consumer.getmany(timeout_ms=1000, max_records=10)
                    for _tp, messages in batches.items():
                        for message in messages:
                            await self._handle(processor, message.value, message.headers)
                    if batches:
                        # Коммит ТОЛЬКО после успешной обработки/пропуска батча.
                        await consumer.commit()
            finally:
                await consumer.stop()
                logger.info("consumer_stopped")

    async def _handle(
        self,
        processor: ImageGenProcessor,
        raw: bytes | None,
        headers: KafkaHeaders | None = None,
    ) -> None:
        """Разбирает конверт и обрабатывает; не бросает (offset коммитится дальше).

        Продолжает трейс из заголовков Kafka (traceparent от Core API) — span
        ``image_gen.process`` становится потомком span'а продюсера дуэли.
        """
        if raw is None:
            logger.warning("empty_message_skipped")
            return
        try:
            event = parse_envelope(raw)
        except EnvelopeError as exc:
            # Битый конверт — повтор разбора бесполезен: лог и пропуск.
            logger.error("envelope_parse_failed", error=str(exc))
            return
        with consume_span("image_gen.process", headers):
            await processor.process_with_retries(event)


async def _amain() -> None:
    configure_logging()
    settings = get_settings()
    init_telemetry(settings)
    consumer = ImageGenConsumer(settings)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, consumer.request_stop)

    logger.info("image_gen_starting", brokers=settings.kafka_brokers)
    await consumer.run()


def main() -> None:
    """Entrypoint: ``python -m src.workers.image_gen``."""
    try:
        asyncio.run(_amain())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
