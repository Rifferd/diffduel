import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import type Redis from 'ioredis';
import { LEAVE_SCRIPT, PAIR_SCRIPT } from '../src/matchmaking/lua-scripts';
import { RedisKeys } from '../src/common/keys';
import { flushTestDb, makeTestRedis } from './helpers/redis';

const TOPIC = 'sql';

describe('Lua matchmaking scripts (real Redis /14)', () => {
  const redis: Redis = makeTestRedis();
  const queue = RedisKeys.mmQueue(TOPIC);
  const meta = RedisKeys.mmMeta(TOPIC);

  beforeEach(async () => {
    await flushTestDb(redis);
  });

  afterAll(async () => {
    await flushTestDb(redis);
    await redis.quit();
  });

  async function enqueue(user: string, elo: number): Promise<void> {
    await redis.zadd(queue, elo, user);
    await redis.hset(meta, user, JSON.stringify({ joined_at: Date.now() }));
  }

  it('pairs both present candidates atomically and removes them', async () => {
    await enqueue('a', 1200);
    await enqueue('b', 1210);

    const res = await redis.eval(PAIR_SCRIPT, 2, queue, meta, 'a', 'b');

    expect(res).toBe(1);
    expect(await redis.zcard(queue)).toBe(0);
    expect(await redis.hlen(meta)).toBe(0);
  });

  it('does not pair (and removes nothing) when one candidate is missing', async () => {
    await enqueue('a', 1200);

    const res = await redis.eval(PAIR_SCRIPT, 2, queue, meta, 'a', 'ghost');

    expect(res).toBe(0);
    // 'a' must remain claimable.
    expect(await redis.zscore(queue, 'a')).not.toBeNull();
    expect(await redis.hget(meta, 'a')).not.toBeNull();
  });

  it('is race-safe: only one of two concurrent pairings on the same user wins', async () => {
    await enqueue('a', 1200);
    await enqueue('b', 1205);
    await enqueue('c', 1210);

    // a-b and a-c race for 'a'. Exactly one must succeed.
    const [r1, r2] = await Promise.all([
      redis.eval(PAIR_SCRIPT, 2, queue, meta, 'a', 'b'),
      redis.eval(PAIR_SCRIPT, 2, queue, meta, 'a', 'c'),
    ]);

    expect([r1, r2].filter((r) => r === 1)).toHaveLength(1);
    // Whichever lost leaves its partner still in the queue.
    expect(await redis.zcard(queue)).toBe(1);
  });

  it('leave removes a user from queue and meta', async () => {
    await enqueue('a', 1200);

    const existed = await redis.eval(LEAVE_SCRIPT, 2, queue, meta, 'a');
    const again = await redis.eval(LEAVE_SCRIPT, 2, queue, meta, 'a');

    expect(existed).toBe(1);
    expect(again).toBe(0);
    expect(await redis.zcard(queue)).toBe(0);
  });
});
