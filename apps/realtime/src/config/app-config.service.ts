import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Env } from './env.schema';

/**
 * Thin, fully-typed wrapper over @nestjs/config. The underlying store is
 * already validated by {@link validateEnv}, so every getter is non-null.
 */
@Injectable()
export class AppConfigService {
  constructor(private readonly config: ConfigService<Env, true>) {}

  private get<K extends keyof Env>(key: K): Env[K] {
    return this.config.get(key, { infer: true });
  }

  get appEnv(): Env['APP_ENV'] {
    return this.get('APP_ENV');
  }

  get isProd(): boolean {
    return this.appEnv === 'prod';
  }

  get port(): number {
    return this.get('PORT');
  }

  get redisUrl(): string {
    return this.get('REDIS_URL');
  }

  get jwtSecret(): string {
    return this.get('JWT_SECRET');
  }

  get internalApiToken(): string {
    return this.get('INTERNAL_API_TOKEN');
  }

  get coreApiUrl(): string {
    return this.get('CORE_API_URL');
  }

  get kafkaBrokers(): string[] {
    return this.get('KAFKA_BROKERS')
      .split(',')
      .map((b) => b.trim())
      .filter(Boolean);
  }

  get corsOrigins(): string[] {
    return this.get('CORS_ORIGINS')
      .split(',')
      .map((o) => o.trim())
      .filter(Boolean);
  }

  get duelTasksCount(): number {
    return this.get('DUEL_TASKS_COUNT');
  }

  get duelTaskSeconds(): number {
    return this.get('DUEL_TASK_SECONDS');
  }
}
