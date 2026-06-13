import { z } from 'zod';

/**
 * Env schema for the realtime service. Names are fixed by docs/specs/duels.md
 * ("Env realtime") and docs/specs/conventions.md. Validated once at startup
 * (fail fast) — see {@link validateEnv}.
 */
export const envSchema = z.object({
  APP_ENV: z.enum(['dev', 'test', 'prod']).default('dev'),
  PORT: z.coerce.number().int().positive().default(8100),

  REDIS_URL: z.string().url().default('redis://localhost:6379/0'),

  // HS256 access-token verification uses the same secret as Core API.
  JWT_SECRET: z.string().min(1, 'JWT_SECRET is required'),

  INTERNAL_API_TOKEN: z.string().min(1, 'INTERNAL_API_TOKEN is required'),
  CORE_API_URL: z.string().url().default('http://localhost:8000'),

  KAFKA_BROKERS: z.string().default('localhost:19092'),

  // Comma-separated allow-list for Socket.IO CORS.
  CORS_ORIGINS: z.string().default('http://localhost:5173,http://localhost:5174'),

  // Duel format — configurable for fast e2e tests; defaults per spec (5 × 30s).
  DUEL_TASKS_COUNT: z.coerce.number().int().positive().default(5),
  DUEL_TASK_SECONDS: z.coerce.number().int().positive().default(30),

  // Observability (ТЗ §3.12). Empty endpoint/DSN = disabled (no-op).
  OTEL_EXPORTER_OTLP_ENDPOINT: z.string().default(''),
  OTEL_SERVICE_NAME: z.string().default('diffduel-realtime'),
  SENTRY_DSN: z.string().default(''),
});

export type Env = z.infer<typeof envSchema>;

export function validateEnv(raw: Record<string, unknown>): Env {
  const parsed = envSchema.safeParse(raw);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join('.') || '(root)'}: ${i.message}`)
      .join('\n');
    throw new Error(`Invalid realtime environment configuration:\n${issues}`);
  }
  return parsed.data;
}
