import { Inject, Injectable, Logger } from '@nestjs/common';
import { REDIS_CLIENT, type RedisClient } from '../redis/redis.constants';
import { RedisKeys } from '../common/keys';
import type {
  AnswerProgressRecord,
  AnswerRecord,
  DuelReason,
  DuelState,
} from '../common/types';
import { DuelStateRepository } from './duel-state.repository';
import { DUEL_EMITTER, type IDuelEmitter } from './duel-emitter.interface';
import { EventsService } from '../events/events.service';
import { EloCacheService } from '../matchmaking/elo-cache.service';
import { INTERNAL_CLIENT, type IInternalClient } from '../internal-client/internal-client.interface';
import { scoreOf } from './scoring';
import { RECORD_ANSWER_SCRIPT } from './lua-scripts';

/** Grace period after deadline during which a late answer is still accepted. */
const GRACE_MS = 1_000;
/** Countdown before the first task. */
const COUNTDOWN_FROM = 3;
const COUNTDOWN_STEP_MS = 1_000;

interface SubmitResult {
  ok: boolean;
  error?: { code: string; message: string };
}

/**
 * Owns the running duel lifecycle: countdown, task progression, answer
 * validation against the Redis-held reference, deadline enforcement and finish.
 *
 * Deadlines are enforced by BOTH a per-duel timer and a time check on submit —
 * the timer may not fire (restart) but a server-time check always rejects late
 * answers. Per-duel timer restoration after a service restart is out of scope
 * for MVP (spec).
 */
@Injectable()
export class DuelEngineService {
  private readonly logger = new Logger(DuelEngineService.name);
  /** Active deadline timers, keyed by duelId. Best-effort, not persisted. */
  private readonly timers = new Map<string, NodeJS.Timeout>();
  /** Guards against concurrent advance() for the same duel. */
  private readonly advancing = new Set<string>();

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: RedisClient,
    private readonly repo: DuelStateRepository,
    @Inject(DUEL_EMITTER) private readonly emitter: IDuelEmitter,
    private readonly events: EventsService,
    private readonly elo: EloCacheService,
    @Inject(INTERNAL_CLIENT) private readonly internal: IInternalClient,
  ) {}

  /** Run countdown then dispatch task 0. Called right after duel.matched. */
  async startDuel(duelId: string): Promise<void> {
    const state = await this.repo.get(duelId);
    if (!state) {
      return;
    }
    for (let n = COUNTDOWN_FROM; n >= 1; n--) {
      for (const player of state.players) {
        this.emitter.toUser(player, 'duel.countdown', { n });
      }
      if (n > 1) {
        await delay(COUNTDOWN_STEP_MS);
      }
    }
    await this.sendTask(duelId, 0);
  }

  /** Send duel.task for the given index and arm its deadline timer. */
  private async sendTask(duelId: string, idx: number): Promise<void> {
    const state = await this.repo.get(duelId);
    if (!state || state.status !== 'running') {
      return;
    }
    const task = state.tasks[idx];
    const now = Date.now();
    const deadline = now + task.time_limit_s * 1000;
    await this.repo.setCurrentTask(duelId, idx, now, deadline);

    for (const player of state.players) {
      this.emitter.toUser(player, 'duel.task', {
        idx,
        body: task.body,
        deadline_ts: deadline,
      });
    }
    this.armTimer(duelId, idx, deadline + GRACE_MS - now);
  }

  private armTimer(duelId: string, idx: number, ms: number): void {
    this.clearTimer(duelId);
    const handle = setTimeout(() => {
      this.timers.delete(duelId);
      void this.onDeadline(duelId, idx);
    }, Math.max(0, ms));
    // Don't keep the event loop alive solely for a duel timer.
    handle.unref?.();
    this.timers.set(duelId, handle);
  }

  private clearTimer(duelId: string): void {
    const existing = this.timers.get(duelId);
    if (existing) {
      clearTimeout(existing);
      this.timers.delete(duelId);
    }
  }

  private async onDeadline(duelId: string, idx: number): Promise<void> {
    const state = await this.repo.get(duelId);
    if (!state || state.status !== 'running' || state.idx !== idx) {
      return;
    }
    await this.advance(duelId);
  }

  /**
   * Handle duel.answer. Accepts an answer only from a participant, for the
   * current idx, once per task, and only until deadline + grace. Time is
   * measured server-side from task_sent_ts.
   */
  async submitAnswer(
    duelId: string,
    userId: string,
    idx: number,
    selected: number,
  ): Promise<SubmitResult> {
    const state = await this.repo.get(duelId);
    if (!state || state.status !== 'running') {
      return fail('duel_not_running', 'Duel is not running');
    }
    if (!state.players.includes(userId)) {
      return fail('not_a_participant', 'You are not a participant of this duel');
    }
    if (idx !== state.idx) {
      return fail('wrong_task', 'Answer is for a non-current task');
    }
    const now = Date.now();
    if (now > state.deadline_ts + GRACE_MS) {
      return fail('deadline_passed', 'Answer arrived after the deadline');
    }

    const task = state.tasks[idx];
    const timeMs = Math.max(0, now - state.task_sent_ts);
    const correct = selected === task.answer;
    const record: AnswerProgressRecord = {
      idx,
      task_id: task.id,
      selected,
      time_ms: timeMs,
      correct,
    };

    // Atomic record: append + already-answered + both-answered in one Redis
    // call, so two simultaneous answers (even across instances) can't clobber
    // each other's progress (read-modify-write race).
    const [a, b] = state.players;
    const result = (await this.redis.eval(
      RECORD_ANSWER_SCRIPT,
      1,
      RedisKeys.duel(duelId),
      userId,
      String(idx),
      JSON.stringify(record),
      a,
      b,
    )) as [string, number];
    const [code, bothAnswered] = result;

    if (code === 'already_answered') {
      return fail('already_answered', 'You already answered this task');
    }
    if (code === 'wrong_task') {
      return fail('wrong_task', 'Answer is for a non-current task');
    }
    if (code !== 'ok') {
      return fail('duel_not_running', 'Duel is not running');
    }

    // Verdict to the author (reveals correctOption only now).
    this.emitter.toUser(userId, 'duel.verdict', {
      idx,
      correct,
      correctOption: task.answer,
      timeMs,
    });
    // Opponent sees timing + correctness, never the selected option.
    this.emitter.toUser(this.opponentOf(state, userId), 'duel.opponent_answered', {
      idx,
      timeMs,
      correct,
    });

    // Best-effort analytics event — does not block the answer path.
    this.events.emitAnswerSubmitted({
      duel_id: duelId,
      user_id: userId,
      task_id: task.id,
      selected,
      correct,
      time_ms: timeMs,
      idx,
    });

    if (bothAnswered === 1) {
      await this.advance(duelId);
    }
    return { ok: true };
  }

  /** Move to the next task or finish. Idempotent per (duelId, idx) via guard. */
  private async advance(duelId: string): Promise<void> {
    if (this.advancing.has(duelId)) {
      return;
    }
    this.advancing.add(duelId);
    try {
      const state = await this.repo.get(duelId);
      if (!state || state.status !== 'running') {
        return;
      }
      this.clearTimer(duelId);

      // Fill missing answers for the just-finished task with null (timed out).
      this.fillMissing(state, state.idx);
      await this.repo.setProgress(duelId, state.progress);

      const nextIdx = state.idx + 1;
      if (nextIdx >= state.tasks.length) {
        await this.finish(duelId, state, this.deriveReason(state));
        return;
      }
      await this.sendTask(duelId, nextIdx);
    } finally {
      this.advancing.delete(duelId);
    }
  }

  /**
   * Finalise the duel: POST finish, emit duel.finished to both (score from each
   * receiver's perspective), refresh elo cache, clear active-duel and the duel
   * hash. Safe to call once; guarded by status flip to 'finished'.
   */
  async finish(duelId: string, state: DuelState, reason: DuelReason): Promise<void> {
    // Flip status first so re-entrant timers/answers bail out.
    if (state.status === 'finished') {
      return;
    }
    await this.repo.setStatus(duelId, 'finished');
    state.status = 'finished';
    this.clearTimer(duelId);

    const [a, b] = state.players;
    const results = {
      [a]: { answers: stripIdx(state.progress[a] ?? []) },
      [b]: { answers: stripIdx(state.progress[b] ?? []) },
    };

    let winnerId: string | null = null;
    let deltas: Record<string, number> = { [a]: 0, [b]: 0 };
    let elo: Record<string, number> = { [a]: state.ratings[a] ?? 0, [b]: state.ratings[b] ?? 0 };

    try {
      const res = await this.internal.finishDuel(duelId, {
        finished_at: new Date().toISOString(),
        results,
        reason,
      });
      winnerId = res.winner_id;
      deltas = res.deltas;
      elo = res.elo;
      await this.elo.setMany(state.topic, res.elo);
    } catch (err) {
      this.logger.error(`finishDuel failed for ${duelId}: ${(err as Error).message}`);
    }

    const scoreA = scoreOf(state.progress[a] ?? []);
    const scoreB = scoreOf(state.progress[b] ?? []);

    this.emitter.toUser(a, 'duel.finished', {
      winnerId,
      deltas,
      elo,
      score: { mine: scoreA.correct, opp: scoreB.correct },
      reason,
    });
    this.emitter.toUser(b, 'duel.finished', {
      winnerId,
      deltas,
      elo,
      score: { mine: scoreB.correct, opp: scoreA.correct },
      reason,
    });

    // Cleanup: active-duel pointers and the duel hash (results screen needs no
    // reconnect, per spec).
    await this.redis.del(
      RedisKeys.userActiveDuel(a),
      RedisKeys.userActiveDuel(b),
    );
    await this.repo.delete(duelId);
  }

  private fillMissing(state: DuelState, idx: number): void {
    const task = state.tasks[idx];
    for (const player of state.players) {
      const list = state.progress[player] ?? [];
      if (!list.some((a) => a.idx === idx)) {
        list.push({
          idx,
          task_id: task.id,
          selected: null,
          time_ms: null,
          correct: false,
        });
      }
      state.progress[player] = list;
    }
  }

  /**
   * Reason for a naturally-finished duel. If neither player gave a single real
   * answer (every selected is null — both abandoned), it's `aborted`; otherwise
   * `completed`. (`opponent_left` would be set by an explicit leave flow.)
   */
  private deriveReason(state: DuelState): DuelReason {
    const anyAnswer = state.players.some((p) =>
      (state.progress[p] ?? []).some((a) => a.selected !== null),
    );
    return anyAnswer ? 'completed' : 'aborted';
  }

  private opponentOf(state: DuelState, userId: string): string {
    return state.players[0] === userId ? state.players[1] : state.players[0];
  }
}

/** Strip the internal `idx` field before sending results to Core API. */
function stripIdx(answers: AnswerProgressRecord[]): AnswerRecord[] {
  return answers.map(({ task_id, selected, time_ms, correct }) => ({
    task_id,
    selected,
    time_ms,
    correct,
  }));
}

function fail(code: string, message: string): SubmitResult {
  return { ok: false, error: { code, message } };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
