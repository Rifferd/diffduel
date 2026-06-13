"""Kafka-продюсер событий (Redpanda в dev).

Конверт события — строго по conventions.md:
``{"v": 1, "type": "...", "occurred_at": iso8601, "payload": {...}}``.

Дизайн:
- ленивый продюсер-синглтон (один на процесс), стартует при первом produce;
- produce best-effort: недоступность брокера НЕ ломает запрос — ошибка только
  логируется (консьюмеры — этап 4, гарантии at-least-once на их стороне);
- закрытие — в lifespan приложения через ``close_producer()``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer
from opentelemetry import propagate

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("events")

_producer: AIOKafkaProducer | None = None
_lock = asyncio.Lock()


def _serialize(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")


async def _get_producer() -> AIOKafkaProducer:
    """Ленивая инициализация продюсера под асинхронным локом."""
    global _producer
    if _producer is None:
        async with _lock:
            if _producer is None:
                settings = get_settings()
                producer = AIOKafkaProducer(
                    bootstrap_servers=settings.kafka_brokers,
                    value_serializer=_serialize,
                    key_serializer=lambda k: k.encode("utf-8"),
                    enable_idempotence=True,
                    acks="all",
                )
                await producer.start()
                _producer = producer
    return _producer


def _envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": event_type,
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "payload": payload,
    }


def _trace_headers() -> list[tuple[str, bytes]]:
    """Инжектит W3C trace-context (``traceparent``) в заголовки Kafka.

    Ключевая демонстрация ТЗ §3.12: трейс продолжается API → Kafka → воркер.
    Если телеметрия выключена (нет активного span) — заголовки пустые (no-op).
    """
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return [(k, v.encode("utf-8")) for k, v in carrier.items()]


async def produce(topic: str, *, key: str, event_type: str, payload: dict[str, Any]) -> None:
    """Best-effort отправка события. Ошибки брокера логируются, не пробрасываются."""
    envelope = _envelope(event_type, payload)
    try:
        producer = await _get_producer()
        await producer.send_and_wait(
            topic, value=envelope, key=key, headers=_trace_headers()
        )
    except Exception:
        # Брокер недоступен — дуэль/запрос не должны падать (спека duels.md).
        logger.warning("event_produce_failed", topic=topic, event_type=event_type, key=key)


async def close_producer() -> None:
    """Останавливает продюсер при остановке приложения (lifespan)."""
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        except Exception:
            logger.warning("event_producer_stop_failed")
        finally:
            _producer = None
