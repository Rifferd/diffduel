import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type {
  DailyAnswerResult,
  DailyLeaderboardEntry,
  DailyMyPosition,
  DailyTask,
} from '@diffduel/contracts';
import { useDailyChallenge } from './useDailyChallenge';
import { dailyApi } from '@/shared/api/endpoints';

const DAILY: DailyTask = {
  challenge_date: '2026-06-14',
  task: {
    id: 't-daily',
    type: 'quiz',
    difficulty: 2,
    body: { question: 'Q?', options: ['a', 'b', 'c'], code: null, language: null, tags: ['js'] },
  },
};

const BOARD: DailyLeaderboardEntry[] = [
  { rank: 1, user_id: 'u1', username: 'masha', avatar_url: null, score: 990 },
];
const MINE: DailyMyPosition = { rank: 3, score: 950 };

function result(over: Partial<DailyAnswerResult> = {}): DailyAnswerResult {
  return {
    correct: true,
    correct_option: 0,
    explanation: 'верно',
    scored: true,
    already_answered: false,
    ...over,
  };
}

describe('useDailyChallenge', () => {
  beforeEach(() => {
    let t = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => {
      t += 1000;
      return t;
    });
    vi.spyOn(dailyApi, 'leaderboard').mockResolvedValue([...BOARD]);
    vi.spyOn(dailyApi, 'me').mockResolvedValue({ ...MINE });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('грузит задачу дня, лидерборд и мою позицию', async () => {
    vi.spyOn(dailyApi, 'get').mockResolvedValue({ ...DAILY });

    const d = useDailyChallenge();
    await d.load();
    await Promise.resolve();
    await Promise.resolve();

    expect(d.phase.value).toBe('answering');
    expect(d.task.value?.id).toBe('t-daily');
    expect(d.challengeDate.value).toBe('2026-06-14');
    expect(d.leaderboard.value).toHaveLength(1);
    expect(d.myPosition.value?.rank).toBe(3);
  });

  it('зачётный ответ: scored=true, переход в result, time_ms в диапазоне', async () => {
    vi.spyOn(dailyApi, 'get').mockResolvedValue({ ...DAILY });
    const answer = vi.spyOn(dailyApi, 'answer').mockResolvedValue(result());

    const d = useDailyChallenge();
    await d.load();
    await d.answer(0);

    expect(d.phase.value).toBe('result');
    expect(d.result.value?.scored).toBe(true);
    expect(d.selected.value).toBe(0);
    const sent = answer.mock.calls[0][0];
    expect(sent.answer).toEqual({ selected: 0 });
    expect(sent.time_ms).toBeGreaterThanOrEqual(100);
    expect(sent.time_ms).toBeLessThanOrEqual(600_000);
  });

  it('повторный ответ: already_answered=true, scored=false показывается', async () => {
    vi.spyOn(dailyApi, 'get').mockResolvedValue({ ...DAILY });
    vi.spyOn(dailyApi, 'answer').mockResolvedValue(
      result({ scored: false, already_answered: true, correct: false }),
    );

    const d = useDailyChallenge();
    await d.load();
    await d.answer(1);

    expect(d.phase.value).toBe('result');
    expect(d.result.value?.already_answered).toBe(true);
    expect(d.result.value?.scored).toBe(false);
  });

  it('ошибка загрузки → фаза error', async () => {
    vi.spyOn(dailyApi, 'get').mockRejectedValue(new Error('network'));

    const d = useDailyChallenge();
    await d.load();

    expect(d.phase.value).toBe('error');
    expect(d.loadError.value).toBeTruthy();
  });
});
