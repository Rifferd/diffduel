import { Inject, Injectable } from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';
import { RedisKeys } from '../common/keys';
import { DuelStateRepository } from './duel-state.repository';
import { DUEL_EMITTER, type IDuelEmitter, type ReconnectStatePayload } from './duel-emitter.interface';
import { scoreOf } from './scoring';

/**
 * Reconnect / lookup helpers around duel state. Pure orchestration; the engine
 * owns mutations.
 */
@Injectable()
export class DuelService {
  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: RedisClient,
    private readonly repo: DuelStateRepository,
    @Inject(DUEL_EMITTER) private readonly emitter: IDuelEmitter,
  ) {}

  async getActiveDuelId(userId: string): Promise<string | null> {
    return this.redis.get(RedisKeys.userActiveDuel(userId));
  }

  /**
   * If the user has a running duel, join their socket(s) to the room and send
   * system.reconnect_state. No-op otherwise. Returns true if reconnected.
   */
  async tryReconnect(userId: string): Promise<boolean> {
    const duelId = await this.getActiveDuelId(userId);
    if (!duelId) {
      return false;
    }
    const state = await this.repo.get(duelId);
    if (!state || state.status !== 'running' || !state.players.includes(userId)) {
      return false;
    }
    await this.emitter.joinDuelRoom(userId, duelId);

    const opponentId = state.players[0] === userId ? state.players[1] : state.players[0];
    const mine = scoreOf(state.progress[userId] ?? []);
    const opp = scoreOf(state.progress[opponentId] ?? []);

    const payload: ReconnectStatePayload = {
      duelId,
      idx: state.idx,
      deadline_ts: state.deadline_ts,
      progress: state.progress[userId] ?? [],
      opponent: {
        username: state.usernames[opponentId] ?? 'opponent',
        elo: state.ratings[opponentId] ?? 0,
      },
      score: { mine: mine.correct, opp: opp.correct },
    };
    this.emitter.toUser(userId, 'system.reconnect_state', payload);
    return true;
  }
}
