import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { nextTick } from 'vue';
import type { TaskPublic, TournamentAnswerResult } from '@diffduel/contracts';
import { useTournamentSession } from './useTournamentSession';
import { tournamentsApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

const TID = '00000000-0000-0000-0000-000000000001';

function task(id: string, question: string, options: string[]): TaskPublic {
  return {
    id,
    type: 'quiz',
    difficulty: 1,
    body: { question, options, code: null, language: null, tags: [] },
  };
}

const TASKS: TaskPublic[] = [task('t1', 'Q1', ['a', 'b']), task('t2', 'Q2', ['c', 'd'])];

function result(over: Partial<TournamentAnswerResult> = {}): TournamentAnswerResult {
  return {
    correct: true,
    correct_option: 0,
    explanation: 'верно',
    scored: true,
    already_answered: false,
    score: 1,
    finished: false,
    ...over,
  };
}

describe('useTournamentSession', () => {
  beforeEach(() => {
    let t = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => {
      t += 1000;
      return t;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('happy-path: грузит задачи турнира, отвечает, копит score, сводка', async () => {
    vi.spyOn(tournamentsApi, 'tasks').mockResolvedValue({ tasks: [...TASKS] });
    const submit = vi
      .spyOn(tournamentsApi, 'submitAnswer')
      .mockResolvedValueOnce(result({ score: 1 }))
      .mockResolvedValueOnce(result({ score: 2, finished: true }));

    const s = useTournamentSession(TID);
    await s.load();
    expect(s.phase.value).toBe('answering');
    expect(s.tasks.value).toHaveLength(2);

    await s.answer(0);
    expect(s.phase.value).toBe('verdict');
    expect(s.verdict.value?.correct).toBe(true);
    expect(s.score.value).toBe(1);
    // submitAnswer вызван с id турнира и задачи.
    expect(submit).toHaveBeenCalledWith(
      TID,
      expect.objectContaining({ task_id: 't1', answer: { selected: 0 } }),
    );

    s.next();
    await s.answer(1);
    s.next();
    expect(s.phase.value).toBe('summary');
    expect(s.summary.value?.total).toBe(2);
    expect(s.summary.value?.correct).toBe(2);
    expect(s.summary.value?.score).toBe(2);
  });

  it('неверный ответ: фиксирует вердикт и верную опцию', async () => {
    vi.spyOn(tournamentsApi, 'tasks').mockResolvedValue({
      tasks: [task('t1', 'Q', ['a', 'b', 'c'])],
    });
    vi.spyOn(tournamentsApi, 'submitAnswer').mockResolvedValue(
      result({ correct: false, correct_option: 2, score: 0 }),
    );

    const s = useTournamentSession(TID);
    await s.load();
    await s.answer(0);

    expect(s.verdict.value?.correct).toBe(false);
    expect(s.verdict.value?.correct_option).toBe(2);
    expect(s.selected.value).toBe(0);

    s.next();
    expect(s.phase.value).toBe('summary');
    expect(s.summary.value?.accuracy).toBe(0);
  });

  it('ошибка загрузки: фаза error, retry грузит снова', async () => {
    const tasks = vi
      .spyOn(tournamentsApi, 'tasks')
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ tasks: [...TASKS] });

    const s = useTournamentSession(TID);
    await s.load();
    expect(s.phase.value).toBe('error');
    expect(s.loadError.value).toBeTruthy();

    await s.load();
    expect(s.phase.value).toBe('answering');
    expect(tasks).toHaveBeenCalledTimes(2);
  });

  it('429 при ответе: человекочитаемая ошибка, фаза остаётся answering', async () => {
    vi.spyOn(tournamentsApi, 'tasks').mockResolvedValue({ tasks: [...TASKS] });
    vi.spyOn(tournamentsApi, 'submitAnswer').mockRejectedValue(
      new ApiRequestError(429, 'rate_limited', 'too many'),
    );

    const s = useTournamentSession(TID);
    await s.load();
    await s.answer(0);
    await nextTick();

    expect(s.phase.value).toBe('answering');
    expect(s.answerError.value).toContain('Подождите минуту');
    expect(s.answered.value).toHaveLength(0);
  });
});
