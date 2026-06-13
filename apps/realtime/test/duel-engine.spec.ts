import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import type Redis from 'ioredis';
import { DuelEngineService } from '../src/duel/duel-engine.service';
import { DuelStateRepository } from '../src/duel/duel-state.repository';
import { EloCacheService } from '../src/matchmaking/elo-cache.service';
import { RedisKeys } from '../src/common/keys';
import type { DuelState } from '../src/common/types';
import { flushTestDb, makeTestRedis } from './helpers/redis';
import {
  FakeEmitter,
  FakeInternalClient,
  fakeEvents,
  makeDuelTasks,
  makeTasks,
} from './helpers/fakes';

const DUEL_ID = 'duel-1';
const A = 'userA';
const B = 'userB';

describe('DuelEngineService (real Redis /14, internal-client mocked)', () => {
  const redis: Redis = makeTestRedis();
  const repo = new DuelStateRepository(redis);
  const elo = new EloCacheService(redis);

  let emitter: FakeEmitter;
  let internal: FakeInternalClient;
  let engine: DuelEngineService;

  async function seedDuel(taskCount: number, timeLimitS = 30): Promise<void> {
    const tasks = makeDuelTasks(taskCount, timeLimitS);
    const now = Date.now();
    const state: DuelState = {
      topic: 'sql',
      players: [A, B],
      tasks,
      idx: 0,
      deadline_ts: now + 30_000,
      task_sent_ts: now,
      progress: { [A]: [], [B]: [] },
      status: 'running',
      usernames: { [A]: 'alice', [B]: 'bob' },
      ratings: { [A]: 1200, [B]: 1200 },
    };
    await repo.create(DUEL_ID, state);
    await redis.set(RedisKeys.userActiveDuel(A), DUEL_ID);
    await redis.set(RedisKeys.userActiveDuel(B), DUEL_ID);
    internal = new FakeInternalClient(DUEL_ID, makeTasks(taskCount, timeLimitS), {
      [A]: 1200,
      [B]: 1200,
    });
    engine = new DuelEngineService(redis, repo, emitter, fakeEvents, elo, internal);
  }

  beforeEach(async () => {
    await flushTestDb(redis);
    emitter = new FakeEmitter();
  });

  afterAll(async () => {
    await flushTestDb(redis);
    await redis.quit();
  });

  it('accepts exactly one answer per task per user', async () => {
    await seedDuel(3);
    // task 0 correct answer is 0 (makeTasks: answer = i % 4)
    const first = await engine.submitAnswer(DUEL_ID, A, 0, 0);
    const second = await engine.submitAnswer(DUEL_ID, A, 0, 1);

    expect(first.ok).toBe(true);
    expect(second.ok).toBe(false);
    expect(second.error?.code).toBe('already_answered');

    const verdicts = emitter.byType<{ correct: boolean }>('duel.verdict', A);
    expect(verdicts).toHaveLength(1);
    expect(verdicts[0].correct).toBe(true);
  });

  it('marks a wrong answer incorrect and reveals correctOption only to the author', async () => {
    await seedDuel(3);
    const res = await engine.submitAnswer(DUEL_ID, A, 0, 2); // wrong (answer=0)
    expect(res.ok).toBe(true);

    const verdict = emitter.byType<{ correct: boolean; correctOption: number }>(
      'duel.verdict',
      A,
    )[0];
    expect(verdict.correct).toBe(false);
    expect(verdict.correctOption).toBe(0);

    // Opponent sees correctness/timing but NOT the selected option.
    const opp = emitter.byType<Record<string, unknown>>('duel.opponent_answered', B)[0];
    expect(opp).toMatchObject({ idx: 0, correct: false });
    expect(opp).not.toHaveProperty('selected');
  });

  it('rejects an answer for a non-current task', async () => {
    await seedDuel(3);
    const res = await engine.submitAnswer(DUEL_ID, A, 1, 1);
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('wrong_task');
  });

  it('rejects answers from non-participants', async () => {
    await seedDuel(3);
    const res = await engine.submitAnswer(DUEL_ID, 'stranger', 0, 0);
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('not_a_participant');
  });

  it('enforces the deadline + grace by server time, not just the timer', async () => {
    await seedDuel(3);
    // Force the stored deadline into the past.
    await redis.hset(RedisKeys.duel(DUEL_ID), 'deadline_ts', String(Date.now() - 5_000));
    const res = await engine.submitAnswer(DUEL_ID, A, 0, 0);
    expect(res.ok).toBe(false);
    expect(res.error?.code).toBe('deadline_passed');
  });

  it('advances to the next task when both answer', async () => {
    await seedDuel(3);
    await engine.submitAnswer(DUEL_ID, A, 0, 0);
    await engine.submitAnswer(DUEL_ID, B, 0, 1);

    const tasks = emitter.byType<{ idx: number }>('duel.task');
    // task idx 1 dispatched after both answered idx 0
    expect(tasks.some((t) => t.idx === 1)).toBe(true);
    const state = await repo.get(DUEL_ID);
    expect(state?.idx).toBe(1);
  });

  it('finishes after the last task and computes score per perspective', async () => {
    await seedDuel(2);
    // idx0 answer=0, idx1 answer=1. A all correct, B all wrong.
    await engine.submitAnswer(DUEL_ID, A, 0, 0);
    await engine.submitAnswer(DUEL_ID, B, 0, 3);
    await engine.submitAnswer(DUEL_ID, A, 1, 1);
    await engine.submitAnswer(DUEL_ID, B, 1, 0);

    expect(internal.finishCalls).toHaveLength(1);
    expect(internal.finishCalls[0].req.reason).toBe('completed');

    const finA = emitter.byType<{ score: { mine: number; opp: number }; winnerId: string }>(
      'duel.finished',
      A,
    )[0];
    const finB = emitter.byType<{ score: { mine: number; opp: number } }>('duel.finished', B)[0];
    expect(finA.score).toEqual({ mine: 2, opp: 0 });
    expect(finB.score).toEqual({ mine: 0, opp: 2 });
    expect(finA.winnerId).toBe(A);

    // Cleanup: active-duel pointers and the duel hash are gone.
    expect(await redis.get(RedisKeys.userActiveDuel(A))).toBeNull();
    expect(await redis.exists(RedisKeys.duel(DUEL_ID))).toBe(0);
    // Elo cache refreshed from finish response.
    expect(await elo.get('sql', A)).toBe(1216);
  });

  it('finishes with reason=aborted when both players give zero answers', async () => {
    // 1 task, 1s limit; nobody answers → deadline timer fires → aborted.
    await seedDuel(1, 1);
    await engine.startDuel(DUEL_ID); // 3s countdown + 1s deadline + 1s grace

    // Wait for the finished emit (bounded).
    await waitFor(() => emitter.byType('duel.finished', A).length > 0, 12000);

    expect(internal.finishCalls).toHaveLength(1);
    expect(internal.finishCalls[0].req.reason).toBe('aborted');
    const fin = emitter.byType<{ score: { mine: number; opp: number } }>('duel.finished', A)[0];
    expect(fin.score).toEqual({ mine: 0, opp: 0 });
  });
});

async function waitFor(pred: () => boolean, timeoutMs: number): Promise<void> {
  const start = Date.now();
  while (!pred()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error('waitFor timed out');
    }
    await new Promise((r) => setTimeout(r, 50));
  }
}
