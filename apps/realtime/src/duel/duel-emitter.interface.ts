/**
 * Port the engine/matchmaking use to push WS events, implemented by the
 * gateway. Decouples domain logic from Socket.IO. Event names/payloads follow
 * docs/specs/duels.md (WebSocket protocol).
 */
export const DUEL_EMITTER = Symbol('DUEL_EMITTER');

export interface MatchedPayload {
  duelId: string;
  topic: string;
  opponent: { username: string; elo: number };
  tasksCount: number;
}

export interface TaskPayload {
  idx: number;
  body: unknown;
  deadline_ts: number;
}

export interface VerdictPayload {
  idx: number;
  correct: boolean;
  correctOption: number;
  timeMs: number | null;
}

export interface OpponentAnsweredPayload {
  idx: number;
  timeMs: number | null;
  correct: boolean;
}

export interface FinishedPayload {
  winnerId: string | null;
  deltas: Record<string, number>;
  elo: Record<string, number>;
  score: { mine: number; opp: number };
  reason: string;
}

export interface ReconnectStatePayload {
  duelId: string;
  idx: number;
  deadline_ts: number;
  progress: unknown;
  opponent: { username: string; elo: number };
  score: { mine: number; opp: number };
}

export interface IDuelEmitter {
  /** Join a socket-less user (all their sockets) into the duel room. */
  joinDuelRoom(userId: string, duelId: string): Promise<void>;
  toUser(userId: string, event: 'duel.matched', payload: MatchedPayload): void;
  toUser(userId: string, event: 'duel.countdown', payload: { n: number }): void;
  toUser(userId: string, event: 'duel.task', payload: TaskPayload): void;
  toUser(userId: string, event: 'duel.verdict', payload: VerdictPayload): void;
  toUser(
    userId: string,
    event: 'duel.opponent_answered',
    payload: OpponentAnsweredPayload,
  ): void;
  toUser(userId: string, event: 'duel.finished', payload: FinishedPayload): void;
  toUser(userId: string, event: 'system.reconnect_state', payload: ReconnectStatePayload): void;
  toUser(userId: string, event: 'system.error', payload: { code: string; message: string }): void;
  toUser(userId: string, event: 'queue.searching', payload: { widening: number }): void;
}
