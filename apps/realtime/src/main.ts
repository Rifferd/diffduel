import 'reflect-metadata';
import { startTelemetry } from './telemetry';

// Start OTel/Sentry BEFORE any instrumented module is imported (no-op when
// OTEL_EXPORTER_OTLP_ENDPOINT / SENTRY_DSN are unset). See telemetry.ts.
startTelemetry();

import { NestFactory } from '@nestjs/core';
import { ConsoleLogger, Logger } from '@nestjs/common';
import { JsonLogger } from './common/json.logger';
import { AppModule } from './app.module';
import { AppConfigService } from './config/app-config.service';
import { RedisIoAdapter } from './gateway/redis-io.adapter';

async function bootstrap(): Promise<void> {
  const logger = new Logger('Bootstrap');
  // JSON structured logs in prod; pretty logs in dev.
  const isProd = process.env.APP_ENV === 'prod';
  const app = await NestFactory.create(AppModule, {
    logger: isProd ? new JsonLogger() : new ConsoleLogger(),
  });

  const config = app.get(AppConfigService);

  // Inputs are validated with Zod at the boundary (gateway handlers), so no
  // global class-validator ValidationPipe is needed.
  app.enableCors({ origin: config.corsOrigins, credentials: true });
  app.enableShutdownHooks();

  const adapter = new RedisIoAdapter(app, config.redisUrl, config.corsOrigins);
  await adapter.connect();
  app.useWebSocketAdapter(adapter);

  await app.listen(config.port, '0.0.0.0');
  logger.log(`realtime listening on :${config.port} (env=${config.appEnv})`);
}

void bootstrap();
