import { Inject, Injectable } from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';
import { DEFAULT_ELO, RedisKeys } from '../common/keys';

/**
 * Per-topic Elo cache (Redis HASH topic -> {userId: elo}). Used to seed the
 * matchmaking score; refreshed after each duel from the finish response.
 * Falls back to {@link DEFAULT_ELO} (1200) on a miss.
 */
@Injectable()
export class EloCacheService {
  constructor(@Inject(REDIS_CLIENT) private readonly redis: RedisClient) {}

  async get(topic: string, userId: string): Promise<number> {
    const raw = await this.redis.hget(RedisKeys.eloCache(topic), userId);
    if (raw === null) {
      return DEFAULT_ELO;
    }
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : DEFAULT_ELO;
  }

  async set(topic: string, userId: string, elo: number): Promise<void> {
    await this.redis.hset(RedisKeys.eloCache(topic), userId, String(elo));
  }

  /** Bulk-update from a finish response `elo` map. */
  async setMany(topic: string, elos: Record<string, number>): Promise<void> {
    const entries = Object.entries(elos);
    if (entries.length === 0) {
      return;
    }
    const flat: string[] = [];
    for (const [userId, elo] of entries) {
      flat.push(userId, String(elo));
    }
    await this.redis.hset(RedisKeys.eloCache(topic), ...flat);
  }
}
