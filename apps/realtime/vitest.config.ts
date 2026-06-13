import { defineConfig } from 'vitest/config';
import swc from 'unplugin-swc';

export default defineConfig({
  // SWC transform so NestJS gets emitted decorator metadata (design:paramtypes)
  // for constructor DI — esbuild alone drops it.
  plugins: [
    swc.vite({
      jsc: {
        parser: { syntax: 'typescript', decorators: true },
        transform: { legacyDecorator: true, decoratorMetadata: true },
        target: 'es2022',
      },
    }),
  ],
  test: {
    globals: true,
    environment: 'node',
    include: ['test/**/*.{test,spec}.ts', 'src/**/*.{test,spec}.ts'],
    // Env required by @nestjs/config at AppModule import time (e2e). Real
    // ConfigModule reads process.env before any top-level test statement runs.
    env: {
      APP_ENV: 'test',
      JWT_SECRET: 'test-secret-test-secret-test-secret-test-secret-test-secret',
      INTERNAL_API_TOKEN: 'test-internal-token',
      REDIS_URL: 'redis://localhost:6379/14',
      KAFKA_BROKERS: 'localhost:19092',
      CORE_API_URL: 'http://localhost:8000',
      DUEL_TASKS_COUNT: '2',
      DUEL_TASK_SECONDS: '30',
    },
    // Engine/e2e/Lua tests hit a real Redis (db 14) and bind a port — keep serial
    // to avoid cross-test key/port contention.
    fileParallelism: false,
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});
