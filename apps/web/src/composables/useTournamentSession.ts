import { computed, ref } from 'vue';
import type { Ref } from 'vue';
import type { TaskPublic, TournamentAnswerResult } from '@diffduel/contracts';
import { tournamentsApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

/** Запись по одному отвеченному вопросу — для сводки в конце. */
export interface AnsweredEntry {
  correct: boolean;
  timeMs: number;
  /** Учтён ли ответ сервером (зачётный). */
  scored: boolean;
}

export interface TournamentSummary {
  total: number;
  correct: number;
  /** Доля верных, 0..100 (целое). */
  accuracy: number;
  /** Среднее время ответа в секундах, округлено до 0.1. */
  avgSeconds: number;
  /** Накопленный score из последнего ответа сервера. */
  score: number;
}

type Phase = 'loading' | 'error' | 'answering' | 'verdict' | 'summary';

export interface UseTournamentSession {
  phase: Ref<Phase>;
  /** Человекочитаемая ошибка загрузки (null, если ошибки нет). */
  loadError: Ref<string | null>;
  /** Текст ошибки при отправке ответа; null — нет. */
  answerError: Ref<string | null>;
  tasks: Ref<TaskPublic[]>;
  index: Ref<number>;
  current: Ref<TaskPublic | null>;
  /** Результат проверки текущего ответа (есть только в фазе verdict). */
  verdict: Ref<TournamentAnswerResult | null>;
  /** Индекс выбранной опции (для подсветки), null до ответа. */
  selected: Ref<number | null>;
  submitting: Ref<boolean>;
  answered: Ref<AnsweredEntry[]>;
  summary: Ref<TournamentSummary | null>;
  /** Накопленный score (из последнего ответа сервера). */
  score: Ref<number>;
  /** Номер текущего вопроса (1-based) — для прогресс-бара. */
  questionNumber: Ref<number>;
  load: () => Promise<void>;
  answer: (selectedOption: number) => Promise<void>;
  next: () => void;
}

function humanizeAnswerError(err: unknown): string {
  if (err instanceof ApiRequestError) {
    if (err.status === 429) {
      return 'Слишком много ответов подряд. Подождите минуту и попробуйте снова.';
    }
    return err.message;
  }
  return 'Не удалось отправить ответ. Проверьте соединение и попробуйте снова.';
}

function humanizeLoadError(err: unknown): string {
  if (err instanceof ApiRequestError) {
    if (err.status === 429) {
      return 'Слишком много запросов. Подождите минуту и попробуйте снова.';
    }
    return err.message;
  }
  return 'Не удалось загрузить задачи турнира. Проверьте соединение и попробуйте снова.';
}

/**
 * Стейт-машина турнирной сессии: loading → answering ⇄ verdict → summary.
 * По образцу useTrainingSession, но ходит в /tournaments/{id}/tasks и /answer.
 * Время ответа меряется от показа задачи до клика (через performance.now()).
 */
export function useTournamentSession(tournamentId: string): UseTournamentSession {
  const phase = ref<Phase>('loading');
  const loadError = ref<string | null>(null);
  const answerError = ref<string | null>(null);
  const tasks = ref<TaskPublic[]>([]);
  const index = ref(0);
  const verdict = ref<TournamentAnswerResult | null>(null);
  const selected = ref<number | null>(null);
  const submitting = ref(false);
  const answered = ref<AnsweredEntry[]>([]);
  const score = ref(0);

  /** Момент показа текущей задачи — основа для time_ms. */
  let shownAt = 0;

  const current = computed<TaskPublic | null>(() => tasks.value[index.value] ?? null);
  const questionNumber = computed(() => index.value + 1);

  const summary = computed<TournamentSummary | null>(() => {
    if (phase.value !== 'summary') return null;
    const entries = answered.value;
    const total = entries.length;
    const correct = entries.filter((e) => e.correct).length;
    const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
    const avgMs = total > 0 ? entries.reduce((s, e) => s + e.timeMs, 0) / total : 0;
    const avgSeconds = Math.round(avgMs / 100) / 10;
    return { total, correct, accuracy, avgSeconds, score: score.value };
  });

  function startQuestionTimer(): void {
    shownAt = performance.now();
  }

  async function load(): Promise<void> {
    phase.value = 'loading';
    loadError.value = null;
    answerError.value = null;
    try {
      const data = await tournamentsApi.tasks(tournamentId);
      tasks.value = data.tasks;
      index.value = 0;
      answered.value = [];
      verdict.value = null;
      selected.value = null;
      score.value = 0;
      if (data.tasks.length === 0) {
        phase.value = 'summary';
        return;
      }
      phase.value = 'answering';
      startQuestionTimer();
    } catch (err) {
      loadError.value = humanizeLoadError(err);
      phase.value = 'error';
    }
  }

  async function answer(selectedOption: number): Promise<void> {
    const task = current.value;
    if (!task || phase.value !== 'answering' || submitting.value) return;

    submitting.value = true;
    answerError.value = null;
    // Клампим в диапазон 100..600000, который требует API.
    const elapsed = Math.round(performance.now() - shownAt);
    const timeMs = Math.min(600_000, Math.max(100, elapsed));

    try {
      const result = await tournamentsApi.submitAnswer(tournamentId, {
        task_id: task.id,
        answer: { selected: selectedOption },
        time_ms: timeMs,
      });
      verdict.value = result;
      selected.value = selectedOption;
      score.value = result.score;
      answered.value.push({ correct: result.correct, timeMs, scored: result.scored });
      phase.value = 'verdict';
    } catch (err) {
      answerError.value = humanizeAnswerError(err);
    } finally {
      submitting.value = false;
    }
  }

  function next(): void {
    if (phase.value !== 'verdict') return;
    verdict.value = null;
    selected.value = null;
    answerError.value = null;
    if (index.value + 1 >= tasks.value.length) {
      phase.value = 'summary';
      return;
    }
    index.value += 1;
    phase.value = 'answering';
    startQuestionTimer();
  }

  return {
    phase,
    loadError,
    answerError,
    tasks,
    index,
    current,
    verdict,
    selected,
    submitting,
    answered,
    summary,
    score,
    questionNumber,
    load,
    answer,
    next,
  };
}
