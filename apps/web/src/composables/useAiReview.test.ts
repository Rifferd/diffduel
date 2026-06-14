import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { effectScope } from 'vue';
import type { AiReviewResponse } from '@diffduel/contracts';
import { useAiReview, type UseAiReview } from './useAiReview';
import { aiReviewApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

function resp(over: Partial<AiReviewResponse> = {}): AiReviewResponse {
  return { status: 'pending', content: null, error: null, ...over };
}

/** Создаёт композабл внутри scope, чтобы onScopeDispose имел контекст. */
function setup(pollIntervalMs = 10): { review: UseAiReview; stop: () => void } {
  const scope = effectScope();
  const review = scope.run(() => useAiReview({ duelId: 'd1', pollIntervalMs })) as UseAiReview;
  return { review, stop: () => scope.stop() };
}

describe('useAiReview', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('пейволл: 402 pro_required при старте → фаза paywall, поллинга нет', async () => {
    const start = vi
      .spyOn(aiReviewApi, 'start')
      .mockRejectedValue(new ApiRequestError(402, 'pro_required', 'Нужен Pro'));
    const get = vi.spyOn(aiReviewApi, 'get');

    const { review: r, stop } = setup();
    await r.start();

    expect(r.phase.value).toBe('paywall');
    expect(start).toHaveBeenCalledWith('d1');
    expect(get).not.toHaveBeenCalled();
    stop();
  });

  it('поллинг: pending → done, content проброшен', async () => {
    vi.spyOn(aiReviewApi, 'start').mockResolvedValue(resp({ status: 'pending' }));
    vi.spyOn(aiReviewApi, 'get')
      .mockResolvedValueOnce(resp({ status: 'pending' }))
      .mockResolvedValueOnce(resp({ status: 'done', content: 'разбор готов' }));

    const { review: r, stop } = setup();
    await r.start();
    expect(r.phase.value).toBe('pending');

    await vi.advanceTimersByTimeAsync(10); // первый poll → pending
    await vi.advanceTimersByTimeAsync(10); // второй poll → done

    expect(r.phase.value).toBe('done');
    expect(r.content.value).toBe('разбор готов');
    stop();
  });

  it('failed: статус failed на старте → фаза failed с текстом ошибки', async () => {
    vi.spyOn(aiReviewApi, 'start').mockResolvedValue(
      resp({ status: 'failed', error: 'ключ недоступен' }),
    );

    const { review: r, stop } = setup();
    await r.start();

    expect(r.phase.value).toBe('failed');
    expect(r.errorText.value).toBe('ключ недоступен');
    stop();
  });
});
