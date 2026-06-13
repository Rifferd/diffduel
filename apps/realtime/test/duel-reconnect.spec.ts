import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import type Redis from 'ioredis';
import { DuelService } from '../src/duel/duel.service';
import { DuelStateRepository } from '../src/duel/duel-state.repository';
import { RedisKeys } from '../src/common/keys';
import type { DuelState } from '../src/common/types';
import { flushTestDb, makeTestRedis } from './helpers/redis';
import { FakeEmitter, makeDuelTasks } from './helpers/fakes';

const DUEL_ID = 'duel-rc';
const A = 'userA';
const B = 'userB';

describe('DuelService reconnect (real Redis /14)', () => {
  const redis: Redis = makeTestRedis();
  const repo = new DuelStateRepository(redis);
  let emitter: FakeEmitter;
  let svc: DuelService;

  async function seedRunningDuel(): Promise<void> {
    const now = Date.now();
    const state: DuelState = {
      topic: 'sql',
      players: [A, B],
      tasks: makeDuelTasks(3),
      idx: 1,
      deadline_ts: now + 10_000,
      task_sent_ts: now,
      progress: {
        [A]: [{ idx: 0, task_id: 'task-0', selected: 0, time_ms: 1200, correct: true }],
        [B]: [{ idx: 0, task_id: 'task-0', selected: 1, time_ms: 1500, correct: false }],
      },
      status: 'running',
      usernames: { [A]: 'alice', [B]: 'bob' },
      ratings: { [A]: 1200, [B]: 1190 },
    };
    await repo.create(DUEL_ID, state);
    await redis.set(RedisKeys.userActiveDuel(A), DUEL_ID);
  }

  beforeEach(async () => {
    await flushTestDb(redis);
    emitter = new FakeEmitter();
    svc = new DuelService(redis, repo, emitter);
  });

  afterAll(async () => {
    await flushTestDb(redis);
    await redis.quit();
  });

  it('rejoins the room and sends system.reconnect_state for a running duel', async () => {
    await seedRunningDuel();

    const reconnected = await svc.tryReconnect(A);

    expect(reconnected).toBe(true);
    expect(emitter.joinedRooms).toContainEqual({ userId: A, duelId: DUEL_ID });

    const snap = emitter.byType<{
      duelId: string;
      idx: number;
      opponent: { username: string; elo: number };
      score: { mine: number; opp: number };
    }>('system.reconnect_state', A)[0];
    expect(snap.duelId).toBe(DUEL_ID);
    expect(snap.idx).toBe(1);
    expect(snap.opponent).toEqual({ username: 'bob', elo: 1190 });
    expect(snap.score).toEqual({ mine: 1, opp: 0 });
  });

  it('is a no-op when the user has no active duel', async () => {
    const reconnected = await svc.tryReconnect('nobody');
    expect(reconnected).toBe(false);
    expect(emitter.events).toHaveLength(0);
  });
});
