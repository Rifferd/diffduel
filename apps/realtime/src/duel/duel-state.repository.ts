import { Inject, Injectable } from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';
import { DUEL_TTL_SECONDS, RedisKeys } from '../common/keys';
import type { DuelProgress, DuelState, DuelStatus, DuelTask } from '../common/types';

/**
 * Reads/writes the duel:{id} HASH. Per spec, fields are: topic, players, tasks
 * (json with answers), idx, deadline_ts, progress(json), status. We also keep
 * task_sent_ts, usernames and ratings for server-side timing and display.
 */
@Injectable()
export class DuelStateRepository {
  constructor(@Inject(REDIS_CLIENT) private readonly redis: RedisClient) {}

  async create(duelId: string, state: DuelState): Promise<void> {
    const key = RedisKeys.duel(duelId);
    await this.redis
      .multi()
      .hset(key, this.serialize(state))
      .expire(key, DUEL_TTL_SECONDS)
      .exec();
  }

  async get(duelId: string): Promise<DuelState | null> {
    const raw = await this.redis.hgetall(RedisKeys.duel(duelId));
    if (!raw || Object.keys(raw).length === 0) {
      return null;
    }
    return this.deserialize(raw);
  }

  /** Advance to the next task: set idx, timing window and reset deadline. */
  async setCurrentTask(
    duelId: string,
    idx: number,
    taskSentTs: number,
    deadlineTs: number,
  ): Promise<void> {
    await this.redis.hset(RedisKeys.duel(duelId), {
      idx: String(idx),
      task_sent_ts: String(taskSentTs),
      deadline_ts: String(deadlineTs),
    });
  }

  async setProgress(duelId: string, progress: DuelProgress): Promise<void> {
    await this.redis.hset(RedisKeys.duel(duelId), 'progress', JSON.stringify(progress));
  }

  async setStatus(duelId: string, status: DuelStatus): Promise<void> {
    await this.redis.hset(RedisKeys.duel(duelId), 'status', status);
  }

  async delete(duelId: string): Promise<void> {
    await this.redis.del(RedisKeys.duel(duelId));
  }

  private serialize(s: DuelState): Record<string, string> {
    return {
      topic: s.topic,
      players: JSON.stringify(s.players),
      tasks: JSON.stringify(s.tasks),
      idx: String(s.idx),
      deadline_ts: String(s.deadline_ts),
      task_sent_ts: String(s.task_sent_ts),
      progress: JSON.stringify(s.progress),
      status: s.status,
      usernames: JSON.stringify(s.usernames),
      ratings: JSON.stringify(s.ratings),
    };
  }

  private deserialize(raw: Record<string, string>): DuelState {
    return {
      topic: raw.topic,
      players: JSON.parse(raw.players) as [string, string],
      tasks: JSON.parse(raw.tasks) as DuelTask[],
      idx: Number(raw.idx),
      deadline_ts: Number(raw.deadline_ts),
      task_sent_ts: Number(raw.task_sent_ts),
      progress: JSON.parse(raw.progress) as DuelProgress,
      status: raw.status as DuelStatus,
      usernames: JSON.parse(raw.usernames ?? '{}') as Record<string, string>,
      ratings: JSON.parse(raw.ratings ?? '{}') as Record<string, number>,
    };
  }
}
