/**
 * OpenTelemetry + Sentry bootstrap for the realtime service.
 *
 * Contract (ТЗ §3.12, ADR-0004):
 * - empty `OTEL_EXPORTER_OTLP_ENDPOINT` => OTel SDK is NOT started (no-op,
 *   zero overhead in the 4GB prod box);
 * - empty `SENTRY_DSN` => Sentry disabled;
 * - this module MUST be imported FIRST in main.ts (before NestFactory and any
 *   instrumented module) so `sdk.start()` patches http/ioredis/socket.io before
 *   they are required. TS emits CommonJS, so the first import runs first.
 *
 * Product metrics (ТЗ §3.12): {@link setWsConnections} feeds a `ws_connections`
 * observable gauge and {@link duelMatchTime} is the duel match-time histogram.
 * Both target the global meter and are no-ops until the SDK installs a real
 * MeterProvider.
 */
import { metrics, type ObservableResult } from '@opentelemetry/api';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-grpc';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';
import * as Sentry from '@sentry/node';

const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? '';
const serviceName = process.env.OTEL_SERVICE_NAME ?? 'diffduel-realtime';
const sentryDsn = process.env.SENTRY_DSN ?? '';

let started = false;

/** Live socket counts per namespace, read by the ws_connections gauge. */
const wsConnectionsByNamespace = new Map<string, number>();

/** Initialise Sentry + OTel SDK. Safe to call once; later calls are no-ops. */
export function startTelemetry(): void {
  if (started) {
    return;
  }
  started = true;

  if (sentryDsn) {
    Sentry.init({ dsn: sentryDsn, environment: process.env.APP_ENV ?? 'dev' });
  }

  if (!endpoint) {
    // No exporter target: skip the SDK entirely (no-op, zero overhead).
    return;
  }

  const sdk = new NodeSDK({
    resource: new Resource({ [ATTR_SERVICE_NAME]: serviceName }),
    traceExporter: new OTLPTraceExporter({ url: endpoint }),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({ url: endpoint }),
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        // Filesystem spans are noisy and irrelevant for a WS service.
        '@opentelemetry/instrumentation-fs': { enabled: false },
      }),
    ],
  });

  sdk.start();
  process.once('SIGTERM', () => void sdk.shutdown().catch(() => undefined));
}

// Self-start at module load: TS emits CommonJS and hoists imports, so calling
// startTelemetry() here (in the first-imported module) runs before NestFactory
// and its instrumented dependencies are required. Idempotent — see the guard.
startTelemetry();

const meter = metrics.getMeter('diffduel.realtime');

meter
  .createObservableGauge('ws_connections', {
    description: 'Active WebSocket connections per namespace',
  })
  .addCallback((result: ObservableResult) => {
    for (const [namespace, value] of wsConnectionsByNamespace) {
      result.observe(value, { namespace });
    }
  });

/** Report the current live-socket count for a namespace (e.g. `/duel`). */
export function setWsConnections(namespace: string, count: number): void {
  wsConnectionsByNamespace.set(namespace, count);
}

/**
 * `duel_match_time_seconds` — histogram of time from queue.join to
 * duel.matched. Recorded by matchmaking on a successful pair.
 */
export const duelMatchTime = meter.createHistogram('duel_match_time_seconds', {
  description: 'Time from queue.join to duel.matched',
  unit: 's',
});
