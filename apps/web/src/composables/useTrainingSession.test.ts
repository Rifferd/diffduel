import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { nextTick } from 'vue';
import type { TaskPublic } from '@diffduel/contracts';
import { useTrainingSession } from './useTrainingSession';
import { tasksApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

function task(id: string, question: string, options: string[]): TaskPublic {
  return {
    id,
    type: 'quiz',
    difficulty: 1,
    body: { question, options, code: null, language: null, tags: [] },
  };
}

const TASKS: TaskPublic[] = [task('t1', 'Q1', ['a', 'b']), task('t2', 'Q2', ['c', 'd'])];

describe('useTrainingSession', () => {
  beforeEach(() => {
    // Стабильное «время»: каждый вызов now() сдвигает на 1000мс.
    let t = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => {
      t += 1000;
      return t;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('happy-path: загружает задачи, верный ответ, переход к следующему, сводка', async () => {
    vi.spyOn(tasksApi, 'training').mockResolvedValue([...TASKS]);
    const submit = vi.spyOn(tasksApi, 'submitAnswer').mockResolvedValue({
      correct: true,
      correct_option: 0,
      explanation: 'верно',
      already_solved: false,
    });

    const s = useTrainingSession({ topic: 'sql', difficulty: 1 });
    await s.load();
    expect(s.phase.value).toBe('answering');
    expect(s.tasks.value).toHaveLength(2);
    expect(s.questionNumber.value).toBe(1);

    await s.answer(0);
    expect(s.phase.value).toBe('verdict');
    expect(s.verdict.value?.correct).toBe(true);
    expect(s.selected.value).toBe(0);
    // time_ms передан в допустимом диапазоне.
    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: 't1', answer: { selected: 0 } }),
    );
    const sentTime = submit.mock.calls[0][0].time_ms;
    expect(sentTime).toBeGreaterThanOrEqual(100);
    expect(sentTime).toBeLessThanOrEqual(600_000);

    s.next();
    expect(s.phase.value).toBe('answering');
    expect(s.questionNumber.value).toBe(2);

    await s.answer(1);
    s.next();
    expect(s.phase.value).toBe('summary');
    expect(s.summary.value?.total).toBe(2);
    expect(s.summary.value?.correct).toBe(2);
  });

  it('неверный ответ: фиксирует вердикт и верную опцию', async () => {
    vi.spyOn(tasksApi, 'training').mockResolvedValue([task('t1', 'Q', ['a', 'b', 'c'])]);
    vi.spyOn(tasksApi, 'submitAnswer').mockResolvedValue({
      correct: false,
      correct_option: 2,
      explanation: 'нет',
      already_solved: false,
    });

    const s = useTrainingSession({ topic: 'sql' });
    await s.load();
    await s.answer(0);

    expect(s.phase.value).toBe('verdict');
    expect(s.verdict.value?.correct).toBe(false);
    expect(s.verdict.value?.correct_option).toBe(2);
    expect(s.selected.value).toBe(0);

    s.next();
    expect(s.phase.value).toBe('summary');
    expect(s.summary.value?.correct).toBe(0);
    expect(s.summary.value?.accuracy).toBe(0);
  });

  it('ошибка сети при загрузке: фаза error, retry грузит снова', async () => {
    const training = vi
      .spyOn(tasksApi, 'training')
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce([...TASKS]);

    const s = useTrainingSession({ topic: 'sql' });
    await s.load();
    expect(s.phase.value).toBe('error');
    expect(s.loadError.value).toBeTruthy();

    await s.load();
    expect(s.phase.value).toBe('answering');
    expect(training).toHaveBeenCalledTimes(2);
  });

  it('429 при ответе: человекочитаемая ошибка, фаза остаётся answering', async () => {
    vi.spyOn(tasksApi, 'training').mockResolvedValue([...TASKS]);
    vi.spyOn(tasksApi, 'submitAnswer').mockRejectedValue(
      new ApiRequestError(429, 'rate_limited', 'too many'),
    );

    const s = useTrainingSession({ topic: 'sql' });
    await s.load();
    await s.answer(0);
    await nextTick();

    expect(s.phase.value).toBe('answering');
    expect(s.answerError.value).toContain('Подождите минуту');
    expect(s.answered.value).toHaveLength(0);
  });

  it('сводка: считает точность и среднее время', async () => {
    vi.spyOn(tasksApi, 'training').mockResolvedValue([
      task('t1', 'Q1', ['a', 'b']),
      task('t2', 'Q2', ['a', 'b']),
      task('t3', 'Q3', ['a', 'b']),
    ]);
    vi.spyOn(tasksApi, 'submitAnswer')
      .mockResolvedValueOnce({
        correct: true,
        correct_option: 0,
        explanation: '',
        already_solved: false,
      })
      .mockResolvedValueOnce({
        correct: false,
        correct_option: 0,
        explanation: '',
        already_solved: false,
      })
      .mockResolvedValueOnce({
        correct: true,
        correct_option: 0,
        explanation: '',
        already_solved: false,
      });

    const s = useTrainingSession({ topic: 'sql' });
    await s.load();
    await s.answer(0);
    s.next();
    await s.answer(1);
    s.next();
    await s.answer(0);
    s.next();

    expect(s.phase.value).toBe('summary');
    expect(s.summary.value?.total).toBe(3);
    expect(s.summary.value?.correct).toBe(2);
    // 2 из 3 = 67%.
    expect(s.summary.value?.accuracy).toBe(67);
    // Каждый ответ занял 1000мс (мок now +1000 на показ, +1000 на клик) => 1.0s.
    expect(s.summary.value?.avgSeconds).toBe(1);
  });
});
