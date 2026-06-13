"""OpenTelemetry + Sentry для воркеров.

Контракт (ТЗ §3.12, ADR-0004):
- пустой ``OTEL_EXPORTER_OTLP_ENDPOINT`` — OTel НЕ инициализируется (no-op);
- пустой ``SENTRY_DSN`` — Sentry выключен;
- метрика ``card_render_latency`` (гистограмма, секунды) — время рендера карточки;
- trace context propagation: трейс продолжается из заголовков Kafka-сообщения
  (см. :func:`extract_context`), демонстрируя сквозной трейс API → Kafka → воркер.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from time import perf_counter

from opentelemetry import context as otel_context
from opentelemetry import metrics, propagate, trace
from opentelemetry.metrics import Histogram
from opentelemetry.trace import Tracer

from src.workers.config import Settings
from src.workers.logging import get_logger

logger = get_logger("telemetry")

_initialized = False
_card_render_latency: Histogram | None = None

# Тип заголовков aiokafka: список (key, value|None).
KafkaHeaders = Iterable[tuple[str, bytes | None]]


def _tracer() -> Tracer:
    return trace.get_tracer("diffduel.workers")


def _render_histogram() -> Histogram:
    global _card_render_latency
    if _card_render_latency is None:
        _card_render_latency = metrics.get_meter("diffduel.workers").create_histogram(
            name="card_render_latency",
            unit="s",
            description="Время рендера share-карточки дуэли",
        )
    return _card_render_latency


def record_card_render(duration_s: float, *, status: str) -> None:
    """Наблюдение в гистограмму card_render_latency. No-op без SDK-провайдера."""
    _render_histogram().record(duration_s, attributes={"status": status})


def extract_context(headers: KafkaHeaders | None) -> otel_context.Context | None:
    """Извлекает W3C trace-context из заголовков Kafka-сообщения.

    Демонстрация trace context propagation (ТЗ §3.12): продюсер Core API
    инжектит ``traceparent`` в заголовки, воркер его извлекает и продолжает
    тот же трейс. Возвращает None, если заголовков нет (телеметрия выключена).
    """
    if not headers:
        return None
    carrier = {k: v.decode("utf-8") for k, v in headers if v is not None}
    if "traceparent" not in carrier:
        return None
    return propagate.extract(carrier)


@contextmanager
def consume_span(name: str, headers: KafkaHeaders | None) -> Iterator[None]:
    """Открывает span-консьюмер, продолжая трейс из заголовков Kafka.

    No-op при выключенной телеметрии (tracer без провайдера — пустые span'ы).
    """
    parent = extract_context(headers)
    with _tracer().start_as_current_span(name, context=parent):
        yield


def init_telemetry(settings: Settings) -> None:
    """Поднимает Sentry + OTel (traces/metrics). No-op без endpoint/DSN."""
    global _initialized
    _init_sentry(settings)

    if not settings.otel_exporter_otlp_endpoint or _initialized:
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
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
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    HTTPXClientInstrumentor().instrument()
    _initialized = True
    logger.info("otel_initialized", service=settings.otel_service_name, endpoint=endpoint)


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,
    )
    logger.info("sentry_initialized", environment=settings.app_env)


class measure_render:  # noqa: N801 — контекст-менеджер в стиле функции
    """Контекст-менеджер: измеряет длительность рендера карточки."""

    def __init__(self) -> None:
        self._start = 0.0
        self.status = "rendered"

    def __enter__(self) -> measure_render:
        self._start = perf_counter()
        return self

    def __exit__(self, exc_type: object, *_exc: object) -> None:
        if exc_type is not None:
            self.status = "failed"
        record_card_render(perf_counter() - self._start, status=self.status)
