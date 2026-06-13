"""OpenTelemetry + Sentry для Core API.

Контракт (ТЗ §3.12, ADR-0004):
- если ``OTEL_EXPORTER_OTLP_ENDPOINT`` пуст — OTel НЕ инициализируется
  (no-op провайдеры SDK по умолчанию, нулевой оверхед в проде на 4GB);
- если пуст ``SENTRY_DSN`` — Sentry выключен;
- авто-инструментирование FastAPI/SQLAlchemy/Redis/aiokafka/httpx включается
  только при заданном endpoint;
- продуктовая метрика ``answer_check_latency`` (гистограмма, секунды) доступна
  всегда через :func:`record_answer_check` — при выключенной телеметрии это
  no-op (используется глобальный meter, который без провайдера ничего не пишет).
"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.metrics import Histogram

from src.core.config import Settings, get_settings
from src.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger("telemetry")

_initialized = False
_answer_check_latency: Histogram | None = None


def _meter() -> metrics.Meter:
    return metrics.get_meter("diffduel.api")


def _get_answer_check_histogram() -> Histogram:
    """Ленивая гистограмма answer_check_latency (секунды)."""
    global _answer_check_latency
    if _answer_check_latency is None:
        _answer_check_latency = _meter().create_histogram(
            name="answer_check_latency",
            unit="s",
            description="Время проверки ответа (соло POST /answers и дуэль)",
        )
    return _answer_check_latency


def record_answer_check(duration_s: float, *, mode: str, correct: bool) -> None:
    """Записывает наблюдение в гистограмму answer_check_latency.

    No-op при выключенной телеметрии: meter без SDK-провайдера ничего не пишет.
    ``mode`` — "solo" | "duel"; ``correct`` — вердикт (для разбивки).
    """
    _get_answer_check_histogram().record(
        duration_s, attributes={"mode": mode, "correct": correct}
    )


def init_sentry(settings: Settings) -> None:
    """Инициализирует Sentry, если задан DSN. Пусто = выключено."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,  # трейсы — через OTel; Sentry только ошибки
    )
    logger.info("sentry_initialized", environment=settings.app_env)


def init_telemetry(app: FastAPI) -> None:
    """Поднимает OTel (traces + metrics) и авто-инструментирование.

    Вызывается из app-factory ОДИН раз. При пустом OTLP endpoint выходит сразу:
    инструментирование не навешивается, оверхед нулевой.
    """
    global _initialized
    settings = get_settings()
    init_sentry(settings)

    if not settings.otel_exporter_otlp_endpoint or _initialized:
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = settings.otel_exporter_otlp_endpoint
    resource = Resource.create({SERVICE_NAME: settings.otel_service_name})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    _instrument(app)
    _initialized = True
    logger.info(
        "otel_initialized",
        service=settings.otel_service_name,
        endpoint=endpoint,
    )


def _instrument(app: FastAPI) -> None:
    """Авто-инструментирование клиентов и FastAPI."""
    from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    AIOKafkaInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()


class measure_answer_check:  # noqa: N801 — контекст-менеджер в стиле функции
    """Контекст-менеджер: измеряет длительность проверки ответа.

    Использование::

        with measure_answer_check(mode="solo") as m:
            result = check_answer(...)
            m.correct = result.correct
    """

    def __init__(self, *, mode: str) -> None:
        self._mode = mode
        self._start = 0.0
        self.correct = False

    def __enter__(self) -> measure_answer_check:
        self._start = perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        record_answer_check(perf_counter() - self._start, mode=self._mode, correct=self.correct)
