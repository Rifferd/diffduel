import { onScopeDispose, ref } from 'vue';
import type { Ref } from 'vue';
import type { AiReviewStatus } from '@diffduel/contracts';
import { aiReviewApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';
import { isProRequired } from '@/shared/api/errors';

/**
 * idle — кнопка «AI-разбор» ещё не нажата.
 * paywall — 402 pro_required: показать пейволл вместо разбора.
 * pending — запрос принят, идёт поллинг GET до done/failed.
 * done/failed — терминальные.
 * error — сетевая/иная ошибка запуска или поллинга.
 */
export type AiReviewPhase = 'idle' | 'paywall' | 'pending' | 'done' | 'failed' | 'error';

export interface UseAiReviewOptions {
  duelId: string;
  /** Интервал поллинга, мс (по умолчанию 2000). */
  pollIntervalMs?: number;
}

export interface UseAiReview {
  phase: Ref<AiReviewPhase>;
  content: Ref<string | null>;
  /** Текст ошибки (failed/error). */
  errorText: Ref<string | null>;
  /** Запустить разбор: POST, затем поллинг. */
  start: () => Promise<void>;
}

function mapStatus(status: AiReviewStatus): AiReviewPhase {
  if (status === 'done') return 'done';
  if (status === 'failed') return 'failed';
  return 'pending';
}

/**
 * AI-разбор дуэли: POST /ai/review/{id}, затем поллинг GET до done/failed.
 * 402 pro_required → фаза paywall. Таймеры чистятся на unmount.
 */
export function useAiReview(options: UseAiReviewOptions): UseAiReview {
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  const phase = ref<AiReviewPhase>('idle');
  const content = ref<string | null>(null);
  const errorText = ref<string | null>(null);

  let pollHandle: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  function clearPoll(): void {
    if (pollHandle !== null) {
      clearTimeout(pollHandle);
      pollHandle = null;
    }
  }

  function applyResult(status: AiReviewStatus, c: string | null, e: string | null): void {
    const mapped = mapStatus(status);
    phase.value = mapped;
    if (mapped === 'done') {
      content.value = c ?? '';
    } else if (mapped === 'failed') {
      errorText.value = e ?? 'AI-разбор не удался. Попробуйте позже.';
    }
  }

  async function poll(): Promise<void> {
    if (stopped) return;
    try {
      const res = await aiReviewApi.get(options.duelId);
      if (stopped) return;
      if (res.status === 'pending') {
        pollHandle = setTimeout(() => void poll(), pollIntervalMs);
        return;
      }
      applyResult(res.status, res.content ?? null, res.error ?? null);
    } catch (err) {
      if (stopped) return;
      errorText.value =
        err instanceof ApiRequestError
          ? err.message
          : 'Не удалось получить разбор. Проверьте соединение.';
      phase.value = 'error';
    }
  }

  async function start(): Promise<void> {
    if (phase.value === 'pending') return;
    clearPoll();
    content.value = null;
    errorText.value = null;
    phase.value = 'pending';
    try {
      const res = await aiReviewApi.start(options.duelId);
      if (res.status === 'pending') {
        pollHandle = setTimeout(() => void poll(), pollIntervalMs);
        return;
      }
      applyResult(res.status, res.content ?? null, res.error ?? null);
    } catch (err) {
      if (isProRequired(err)) {
        phase.value = 'paywall';
        return;
      }
      errorText.value =
        err instanceof ApiRequestError
          ? err.message
          : 'Не удалось запустить разбор. Попробуйте позже.';
      phase.value = 'error';
    }
  }

  function dispose(): void {
    stopped = true;
    clearPoll();
  }

  onScopeDispose(dispose);

  return { phase, content, errorText, start };
}
