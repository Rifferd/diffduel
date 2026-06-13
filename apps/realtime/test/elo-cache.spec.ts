import { afterAll, beforeEach, describe, expect, it } from 'vitest';
import type Redis from 'ioredis';
import { EloCacheService } from '../src/matchmaking/elo-cache.service';
import { DEFAULT_ELO } from '../src/common/keys';
import { flushTestDb, makeTestRedis } from './helpers/redis';

describe('EloCacheService (real Redis /14)', () => {
  const redis: Redis = makeTestRedis();
  const elo = new EloCacheService(redis);

  beforeEach(async () => {
    await flushTestDb(redis);
  });

  afterAll(async () => {
    await flushTestDb(redis);
    await redis.quit();
  });

  it('returns default 1200 on a miss', async () => {
    expect(await elo.get('sql', 'u1')).toBe(DEFAULT_ELO);
  });

  it('stores and reads back a single rating', async () => {
    await elo.set('sql', 'u1', 1340);
    expect(await elo.get('sql', 'u1')).toBe(1340);
    // isolated per topic
    expect(await elo.get('js', 'u1')).toBe(DEFAULT_ELO);
  });

  it('bulk-updates from a finish elo map', async () => {
    await elo.setMany('sql', { u1: 1224, u2: 1176 });
    expect(await elo.get('sql', 'u1')).toBe(1224);
    expect(await elo.get('sql', 'u2')).toBe(1176);
  });

  it('falls back to default on a corrupt value', async () => {
    await redis.hset('elo:sql', 'u1', 'not-a-number');
    expect(await elo.get('sql', 'u1')).toBe(DEFAULT_ELO);
  });
});
