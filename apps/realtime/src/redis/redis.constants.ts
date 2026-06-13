import Redis from 'ioredis';

export type RedisClient = Redis;

export const REDIS_CLIENT = Symbol('REDIS_CLIENT');

export function createRedisClient(url: string): RedisClient {
  return new Redis(url, {
    // Surface connectivity issues early instead of buffering forever.
    maxRetriesPerRequest: 3,
    lazyConnect: false,
  });
}
