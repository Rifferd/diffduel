import { Injectable, Logger } from '@nestjs/common';
import { request } from 'undici';
import { AppConfigService } from '../config/app-config.service';
import type { IInternalClient } from './internal-client.interface';
import type {
  CreateDuelRequest,
  CreateDuelResponse,
  FinishDuelRequest,
  FinishDuelResponse,
} from './internal-client.types';

const TIMEOUT_MS = 5_000;
const MAX_RETRIES = 2; // total attempts = 1 + MAX_RETRIES

/**
 * HTTP client to Core API `/internal/*`. Auth via X-Internal-Token, 5s timeout,
 * up to 2 retries on network errors / 5xx. `finish` is idempotent on the API
 * side, so retrying it is safe.
 */
@Injectable()
export class InternalClientService implements IInternalClient {
  private readonly logger = new Logger(InternalClientService.name);

  constructor(private readonly config: AppConfigService) {}

  createDuel(req: CreateDuelRequest): Promise<CreateDuelResponse> {
    return this.post<CreateDuelResponse>('/internal/duels', req);
  }

  finishDuel(duelId: string, req: FinishDuelRequest): Promise<FinishDuelResponse> {
    return this.post<FinishDuelResponse>(
      `/internal/duels/${encodeURIComponent(duelId)}/finish`,
      req,
    );
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const url = `${this.config.coreApiUrl}${path}`;
    let lastErr: unknown;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res = await request(url, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'x-internal-token': this.config.internalApiToken,
          },
          body: JSON.stringify(body),
          headersTimeout: TIMEOUT_MS,
          bodyTimeout: TIMEOUT_MS,
        });

        if (res.statusCode >= 500) {
          // Drain body so the socket can be reused, then retry.
          await res.body.text();
          throw new RetryableHttpError(res.statusCode);
        }
        if (res.statusCode >= 400) {
          const text = await res.body.text();
          throw new Error(`Core API ${path} -> ${res.statusCode}: ${text}`);
        }
        return (await res.body.json()) as T;
      } catch (err) {
        lastErr = err;
        const retryable = err instanceof RetryableHttpError || isNetworkError(err);
        if (!retryable || attempt === MAX_RETRIES) {
          break;
        }
        const backoff = 100 * (attempt + 1);
        this.logger.warn(
          `${path} attempt ${attempt + 1} failed (${(err as Error).message}); retrying in ${backoff}ms`,
        );
        await delay(backoff);
      }
    }
    throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
  }
}

class RetryableHttpError extends Error {
  constructor(status: number) {
    super(`Core API responded ${status}`);
    this.name = 'RetryableHttpError';
  }
}

function isNetworkError(err: unknown): boolean {
  if (err instanceof RetryableHttpError) {
    return true;
  }
  // undici surfaces ECONNREFUSED/timeouts as Error with a `code` or cause.
  const code = (err as { code?: string })?.code;
  if (typeof code === 'string') {
    return true;
  }
  const cause = (err as { cause?: { code?: string } })?.cause;
  return typeof cause?.code === 'string';
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
