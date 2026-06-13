import {
  Inject,
  Injectable,
  Logger,
  type OnModuleDestroy,
  type OnModuleInit,
} from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';
import { DUEL_TTL_SECONDS, RedisKeys } from '../common/keys';
import { AppConfigService } from '../config/app-config.service';
import { EloCacheService } from './elo-cache.service';
import { LEAVE_SCRIPT, PAIR_SCRIPT } from './lua-scripts';
import { DuelStateRepository } from '../duel/duel-state.repository';
import { DuelEngineService } from '../duel/duel-engine.service';
import { DUEL_EMITTER, type IDuelEmitter } from '../duel/duel-emitter.interface';
import { INTERNAL_CLIENT, type IInternalClient } from '../internal-client/internal-client.interface';
import type { DuelProgress, DuelState, DuelTask } from '../common/types';
import { duelMatchTime } from '../telemetry';

const TICK_MS = 1_000;
const BASE_WINDOW = 150;
const WINDOW_STEP = 150;
const WINDOW_STEP_MS = 5_000;
const MAX_WINDOW = 600;
const JOIN_RATE_LIMIT = 10;
const JOIN_RATE_WINDOW_S = 60;

interface JoinResult {
  ok: boolean;
  error?: { code: string; message: string };
}

interface QueueMeta {
  joined_at: number;
  username: string;
  /** last `widening` step already announced via queue.searching */
  widening: number;
}

/**
 * Matchmaking: per-user join (validated upstream), Redis ZSET queue keyed by
 * elo, a 1s loop that widens the search window over time and pairs candidates
 * atomically via a Lua script, and duel creation on a successful pair.
 */
@Injectable()
export class MatchmakingService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(MatchmakingService.name);
  private loop: NodeJS.Timeout | null = null;
  /** Topics with at least one waiting player; loop only scans these. */
  private readonly activeTopics = new Set<string>();

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: RedisClient,
    private readonly config: AppConfigService,
    private readonly elo: EloCacheService,
    private readonly repo: DuelStateRepository,
    private readonly engine: DuelEngineService,
    @Inject(DUEL_EMITTER) private readonly emitter: IDuelEmitter,
    @Inject(INTERNAL_CLIENT) private readonly internal: IInternalClient,
  ) {}

  onModuleInit(): void {
    this.loop = setInterval(() => void this.tick(), TICK_MS);
    this.loop.unref?.();
  }

  onModuleDestroy(): void {
    if (this.loop) {
      clearInterval(this.loop);
      this.loop = null;
    }
  }

  /**
   * Enqueue a user. Enforces: one active queue/duel per user, 10 joins/min,
   * elo from cache (default 1200). Stores meta for window widening.
   */
  async join(userId: string, username: string, topic: string): Promise<JoinResult> {
    // One active queue/duel per user.
    const activeDuel = await this.redis.get(RedisKeys.userActiveDuel(userId));
    if (activeDuel) {
      return fail('already_in_duel', 'You already have an active duel');
    }
    if (!(await this.checkRate(userId))) {
      return fail('rate_limited', 'Too many queue joins; slow down');
    }

    const elo = await this.elo.get(topic, userId);
    const meta: QueueMeta = { joined_at: Date.now(), username, widening: 0 };
    await this.redis
      .multi()
      .zadd(RedisKeys.mmQueue(topic), elo, userId)
      .hset(RedisKeys.mmMeta(topic), userId, JSON.stringify(meta))
      .exec();
    this.activeTopics.add(topic);
    return { ok: true };
  }

  /** Remove a user from a topic queue atomically (queue.leave / disconnect). */
  async leave(userId: string, topic: string): Promise<void> {
    await this.redis.eval(
      LEAVE_SCRIPT,
      2,
      RedisKeys.mmQueue(topic),
      RedisKeys.mmMeta(topic),
      userId,
    );
  }

  /** Remove a user from every known active topic (disconnect path). */
  async leaveAll(userId: string): Promise<void> {
    for (const topic of this.activeTopics) {
      await this.leave(userId, topic);
    }
  }

  private async checkRate(userId: string): Promise<boolean> {
    const key = RedisKeys.joinRate(userId);
    const count = await this.redis.incr(key);
    if (count === 1) {
      await this.redis.expire(key, JOIN_RATE_WINDOW_S);
    }
    return count <= JOIN_RATE_LIMIT;
  }

  /** One matchmaking tick across all active topics. */
  async tick(): Promise<void> {
    for (const topic of [...this.activeTopics]) {
      try {
        await this.tickTopic(topic);
      } catch (err) {
        this.logger.error(`tick(${topic}) failed: ${(err as Error).message}`);
      }
    }
  }

  private async tickTopic(topic: string): Promise<void> {
    const queueKey = RedisKeys.mmQueue(topic);
    const metaKey = RedisKeys.mmMeta(topic);

    // Members in elo order; member,score pairs.
    const flat = await this.redis.zrange(queueKey, 0, -1, 'WITHSCORES');
    if (flat.length === 0) {
      this.activeTopics.delete(topic);
      return;
    }
    const entries: Array<{ userId: string; elo: number }> = [];
    for (let i = 0; i < flat.length; i += 2) {
      entries.push({ userId: flat[i], elo: Number(flat[i + 1]) });
    }

    const now = Date.now();
    const paired = new Set<string>();

    for (const me of entries) {
      if (paired.has(me.userId)) {
        continue;
      }
      const meta = await this.readMeta(metaKey, me.userId);
      if (!meta) {
        continue;
      }
      const window = this.windowFor(now - meta.joined_at);
      await this.announceWidening(me.userId, meta, metaKey, window);

      // Nearest candidate within window, excluding self/already-paired.
      const candidates = await this.redis.zrangebyscore(
        queueKey,
        me.elo - window,
        me.elo + window,
      );
      const candidate = candidates.find((c) => c !== me.userId && !paired.has(c));
      if (!candidate) {
        continue;
      }

      // Read candidate meta BEFORE pairing — PAIR_SCRIPT HDELs it.
      const candMeta = await this.readMeta(metaKey, candidate);
      const ok = await this.redis.eval(PAIR_SCRIPT, 2, queueKey, metaKey, me.userId, candidate);
      if (ok === 1) {
        paired.add(me.userId);
        paired.add(candidate);
        await this.createDuel(topic, me, candidate, meta, candMeta);
      }
    }

    if ((await this.redis.zcard(queueKey)) === 0) {
      this.activeTopics.delete(topic);
    }
  }

  private windowFor(waitedMs: number): number {
    const steps = Math.floor(waitedMs / WINDOW_STEP_MS);
    return Math.min(MAX_WINDOW, BASE_WINDOW + steps * WINDOW_STEP);
  }

  private async announceWidening(
    userId: string,
    meta: QueueMeta,
    metaKey: string,
    window: number,
  ): Promise<void> {
    const widening = Math.floor((window - BASE_WINDOW) / WINDOW_STEP);
    if (widening > meta.widening) {
      meta.widening = widening;
      await this.redis.hset(metaKey, userId, JSON.stringify(meta));
      this.emitter.toUser(userId, 'queue.searching', { widening });
    }
  }

  private async readMeta(metaKey: string, userId: string): Promise<QueueMeta | null> {
    const raw = await this.redis.hget(metaKey, userId);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as QueueMeta;
    } catch {
      return null;
    }
  }

  /** Create the duel via Core API, persist Redis state, notify + start. */
  private async createDuel(
    topic: string,
    a: { userId: string; elo: number },
    bUserId: string,
    aMeta: QueueMeta,
    bMeta: QueueMeta | null,
  ): Promise<void> {
    const created = await this.internal.createDuel({
      topic,
      player_a: a.userId,
      player_b: bUserId,
    });
    const duelId = created.duel_id;

    // Product metric (ТЗ §3.12): time from queue.join to duel.matched, per
    // player. No-op until the OTel SDK installs a real MeterProvider.
    const matchedAt = Date.now();
    duelMatchTime.record((matchedAt - aMeta.joined_at) / 1000, { topic });
    if (bMeta) {
      duelMatchTime.record((matchedAt - bMeta.joined_at) / 1000, { topic });
    }

    const usernames: Record<string, string> = {
      [a.userId]: aMeta.username,
      [bUserId]: bMeta?.username ?? 'opponent',
    };
    const progress: DuelProgress = { [a.userId]: [], [bUserId]: [] };

    // Cap tasks to configured format (defaults 5) for fast e2e tests.
    // Нормализуем эталон Core API {"correct": idx} в число — движок сверяет
    // выбранную опцию напрямую (DuelTask.answer: number).
    const tasks: DuelTask[] = created.tasks
      .slice(0, this.config.duelTasksCount)
      .map((t) => ({
        id: t.id,
        type: t.type,
        difficulty: t.difficulty,
        body: t.body,
        answer: t.answer.correct,
        time_limit_s: t.time_limit_s,
      }));

    const now = Date.now();
    const state: DuelState = {
      topic,
      players: [a.userId, bUserId],
      tasks,
      idx: 0,
      deadline_ts: now,
      task_sent_ts: now,
      progress,
      status: 'running',
      usernames,
      ratings: created.ratings,
    };
    await this.repo.create(duelId, state);
    await this.redis.set(RedisKeys.userActiveDuel(a.userId), duelId, 'EX', DUEL_TTL_SECONDS);
    await this.redis.set(RedisKeys.userActiveDuel(bUserId), duelId, 'EX', DUEL_TTL_SECONDS);

    // Join both into the duel room, then announce.
    await this.emitter.joinDuelRoom(a.userId, duelId);
    await this.emitter.joinDuelRoom(bUserId, duelId);

    const eloA = created.ratings[a.userId] ?? a.elo;
    const eloB = created.ratings[bUserId] ?? 0;
    this.emitter.toUser(a.userId, 'duel.matched', {
      duelId,
      topic,
      opponent: { username: usernames[bUserId], elo: eloB },
      tasksCount: tasks.length,
    });
    this.emitter.toUser(bUserId, 'duel.matched', {
      duelId,
      topic,
      opponent: { username: usernames[a.userId], elo: eloA },
      tasksCount: tasks.length,
    });

    await this.engine.startDuel(duelId);
  }
}

function fail(code: string, message: string): JoinResult {
  return { ok: false, error: { code, message } };
}
