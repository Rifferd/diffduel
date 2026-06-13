import Redis from 'ioredis';

/** Dedicated test DB (/14) per the task spec, isolated from app data. */
export const TEST_REDIS_URL = 'redis://localhost:6379/14';

export function makeTestRedis(): Redis {
  return new Redis(TEST_REDIS_URL, { maxRetriesPerRequest: 3, lazyConnect: false });
}

export async function flushTestDb(redis: Redis): Promise<void> {
  await redis.flushdb();
}
