/** Shared domain types for the realtime service. */

export type DuelReason = 'completed' | 'opponent_left' | 'aborted';

export type DuelStatus = 'running' | 'finished';

/** A single task as returned by Core API `POST /internal/duels` (with answer). */
export interface DuelTask {
  id: string;
  type: string;
  difficulty: number;
  /** Public statement shown to the client. Arbitrary JSON, like solo mode. */
  body: unknown;
  /** Reference answer — Redis-only, never sent to clients. */
  answer: number;
  time_limit_s: number;
}

/** One player's answer to one task — the shape sent to Core API `finish`. */
export interface AnswerRecord {
  task_id: string;
  selected: number | null;
  time_ms: number | null;
  correct: boolean;
}

/** Internal progress record: an AnswerRecord plus its task index. */
export interface AnswerProgressRecord extends AnswerRecord {
  idx: number;
}

/** progress(json) inside the duel hash: userId -> answers[]. */
export type DuelProgress = Record<string, AnswerProgressRecord[]>;

/**
 * Deserialised duel:{id} HASH. Persisted fields are stringified; this is the
 * in-memory shape after parsing.
 */
export interface DuelState {
  topic: string;
  /** [playerA, playerB] */
  players: [string, string];
  tasks: DuelTask[];
  idx: number;
  /** Server deadline for the current task (epoch ms). */
  deadline_ts: number;
  /** When the current task was sent (epoch ms) — used to measure answer time. */
  task_sent_ts: number;
  progress: DuelProgress;
  status: DuelStatus;
  /** Per-player display name + starting elo, captured at match time. */
  usernames: Record<string, string>;
  ratings: Record<string, number>;
}
