import { ref } from 'vue';
import type { Ref } from 'vue';
import type {
  DailyAnswerResult,
  DailyLeaderboardEntry,
  DailyMyPosition,
  TaskPublic,
} from '@diffduel/contracts';
import { dailyApi } from '@/shared/api/endpoints';
import { ApiRequestError } from '@/shared/api/client';

type Phase = 'loading' | 'error' | 'answering' | 'result';

export interface UseDailyChallenge {
  phase: Ref<Phase>;
  loadError: Ref<string | null>;
  answerError: Ref<string | null>;
  challengeDate: Ref<string | null>;
  task: Ref<TaskPublic | null>;
  /** Выбранная опция (для подсветки), null до ответа. */
  selected: Ref<number | null>;
  submitting: Ref<boolean>;
  result: Ref<DailyAnswerResult | null>;
  leaderboard: Ref<DailyLeaderboardEntry[]>;
  myPosition: Ref<DailyMyPosition | null>;
  load: () => Promise<void>;
  answer: (selectedOption: number) => Promise<void>;
}

function humanize(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError) {
    if (err.status === 429) {
      return 'Слишком много запросов. Подождите минуту и попробуйте снова.';
    }
    return err.message;
  }
  return fallback;
}

/**
 * Стейт-машина задачи дня: loading → answering → result.
 * Один зачётный ответ в день (повторный вернётся already_answered, но результат покажем).
 * Лидерборд и моя позиция тянутся при загрузке и обновляются после ответа.
 */
export function useDailyChallenge(): UseDailyChallenge {
  const phase = ref<Phase>('loading');
  const loadError = ref<string | null>(null);
  const answerError = ref<string | null>(null);
  const challengeDate = ref<string | null>(null);
  const task = ref<TaskPublic | null>(null);
  const selected = ref<number | null>(null);
  const submitting = ref(false);
  const result = ref<DailyAnswerResult | null>(null);
  const leaderboard = ref<DailyLeaderboardEntry[]>([]);
  const myPosition = ref<DailyMyPosition | null>(null);

  /** Момент показа задачи — основа для time_ms. */
  let shownAt = 0;

  async function refreshLeaderboard(): Promise<void> {
    try {
      const [board, mine] = await Promise.all([dailyApi.leaderboard(10), dailyApi.me()]);
      leaderboard.value = board;
      myPosition.value = mine;
    } catch {
      // Лидерборд второстепенен — молча игнорируем ошибку, оставляя пустым.
    }
  }

  async function load(): Promise<void> {
    phase.value = 'loading';
    loadError.value = null;
    answerError.value = null;
    result.value = null;
    selected.value = null;
    try {
      const daily = await dailyApi.get();
      challengeDate.value = daily.challenge_date;
      task.value = daily.task;
      phase.value = 'answering';
      shownAt = performance.now();
      void refreshLeaderboard();
    } catch (err) {
      loadError.value = humanize(err, 'Не удалось загрузить задачу дня. Попробуйте позже.');
      phase.value = 'error';
    }
  }

  async function answer(selectedOption: number): Promise<void> {
    if (!task.value || phase.value !== 'answering' || submitting.value) return;
    submitting.value = true;
    answerError.value = null;
    const elapsed = Math.round(performance.now() - shownAt);
    const timeMs = Math.min(600_000, Math.max(100, elapsed));
    try {
      const res = await dailyApi.answer({
        answer: { selected: selectedOption },
        time_ms: timeMs,
      });
      result.value = res;
      selected.value = selectedOption;
      phase.value = 'result';
      void refreshLeaderboard();
    } catch (err) {
      answerError.value = humanize(err, 'Не удалось отправить ответ. Попробуйте снова.');
    } finally {
      submitting.value = false;
    }
  }

  return {
    phase,
    loadError,
    answerError,
    challengeDate,
    task,
    selected,
    submitting,
    result,
    leaderboard,
    myPosition,
    load,
    answer,
  };
}
