import type { AnswerRecord, DuelReason } from '../common/types';

export interface CreateDuelRequest {
  topic: string;
  player_a: string;
  player_b: string;
}

export interface CreateDuelTask {
  id: string;
  type: string;
  difficulty: number;
  body: unknown;
  /**
   * Эталон в формате Core API (как в соло-режиме): {"correct": <индекс опции>}.
   * Realtime нормализует его в число при построении состояния (DuelTask.answer).
   */
  answer: { correct: number };
  time_limit_s: number;
}

export interface CreateDuelResponse {
  duel_id: string;
  topic: string;
  tasks: CreateDuelTask[];
  ratings: Record<string, number>;
}

export interface FinishDuelRequest {
  finished_at: string;
  results: Record<string, { answers: AnswerRecord[] }>;
  reason: DuelReason;
}

export interface FinishDuelResponse {
  winner_id: string | null;
  deltas: Record<string, number>;
  elo: Record<string, number>;
}
