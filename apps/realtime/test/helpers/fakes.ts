import type { IDuelEmitter } from '../../src/duel/duel-emitter.interface';
import type { IInternalClient } from '../../src/internal-client/internal-client.interface';
import type {
  CreateDuelRequest,
  CreateDuelResponse,
  FinishDuelRequest,
  FinishDuelResponse,
} from '../../src/internal-client/internal-client.types';
import type { EventsService } from '../../src/events/events.service';
import type { DuelTask } from '../../src/common/types';

export interface RecordedEvent {
  userId: string;
  event: string;
  payload: unknown;
}

/** Captures every emit; used to assert protocol output without Socket.IO. */
export class FakeEmitter implements IDuelEmitter {
  readonly events: RecordedEvent[] = [];
  readonly joinedRooms: Array<{ userId: string; duelId: string }> = [];

  async joinDuelRoom(userId: string, duelId: string): Promise<void> {
    this.joinedRooms.push({ userId, duelId });
  }

  toUser(userId: string, event: string, payload: unknown): void {
    this.events.push({ userId, event, payload });
  }

  /** All events of a type, optionally filtered by user. */
  byType<T = unknown>(event: string, userId?: string): T[] {
    return this.events
      .filter((e) => e.event === event && (userId === undefined || e.userId === userId))
      .map((e) => e.payload as T);
  }

  clear(): void {
    this.events.length = 0;
    this.joinedRooms.length = 0;
  }
}

/** No-op events service (Kafka producer) for tests. */
export const fakeEvents = {
  emitAnswerSubmitted(): void {
    /* no-op */
  },
} as unknown as EventsService;

/** In-memory internal client. createDuel returns the configured tasks/ratings;
 * finishDuel computes a winner from the submitted results. */
export class FakeInternalClient implements IInternalClient {
  createCalls: CreateDuelRequest[] = [];
  finishCalls: Array<{ duelId: string; req: FinishDuelRequest }> = [];

  constructor(
    private readonly duelId: string,
    private readonly tasks: CreateDuelResponse['tasks'],
    private readonly ratings: Record<string, number>,
  ) {}

  async createDuel(req: CreateDuelRequest): Promise<CreateDuelResponse> {
    this.createCalls.push(req);
    return {
      duel_id: this.duelId,
      topic: req.topic,
      tasks: this.tasks,
      ratings: this.ratings,
    };
  }

  async finishDuel(duelId: string, req: FinishDuelRequest): Promise<FinishDuelResponse> {
    this.finishCalls.push({ duelId, req });
    const players = Object.keys(req.results);
    const correctCount = (uid: string): number =>
      req.results[uid].answers.filter((a) => a.correct).length;
    const [pa, pb] = players;
    let winnerId: string | null = null;
    if (req.reason !== 'aborted') {
      const ca = correctCount(pa);
      const cb = correctCount(pb);
      if (ca > cb) winnerId = pa;
      else if (cb > ca) winnerId = pb;
    }
    const deltas: Record<string, number> = {};
    const elo: Record<string, number> = {};
    for (const uid of players) {
      const delta = winnerId === null ? 0 : uid === winnerId ? 16 : -16;
      deltas[uid] = delta;
      elo[uid] = (this.ratings[uid] ?? 1200) + delta;
    }
    return { winner_id: winnerId, deltas, elo };
  }
}

/** Задачи в форме ответа Core API (эталон — объект {correct}); для FakeInternalClient/e2e. */
export function makeTasks(n: number, timeLimitS = 30): CreateDuelResponse['tasks'] {
  return Array.from({ length: n }, (_, i) => ({
    id: `task-${i}`,
    type: 'quiz',
    difficulty: 1,
    body: { q: `question ${i}`, options: [0, 1, 2, 3] },
    answer: { correct: i % 4 }, // correct option rotates
    time_limit_s: timeLimitS,
  }));
}

/** Нормализованные задачи (эталон — число) для прямого посева DuelState в тестах движка. */
export function makeDuelTasks(n: number, timeLimitS = 30): DuelTask[] {
  return makeTasks(n, timeLimitS).map((t) => ({
    id: t.id,
    type: t.type,
    difficulty: t.difficulty,
    body: t.body,
    answer: t.answer.correct,
    time_limit_s: t.time_limit_s,
  }));
}
