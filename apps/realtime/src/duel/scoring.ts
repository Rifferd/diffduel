import type { AnswerRecord } from '../common/types';

export interface PlayerScore {
  /** Number of correct answers. */
  correct: number;
  /** Sum of time_ms over correct answers (tie-break). */
  totalTimeMs: number;
}

export function scoreOf(answers: AnswerRecord[]): PlayerScore {
  let correct = 0;
  let totalTimeMs = 0;
  for (const a of answers) {
    if (a.correct) {
      correct += 1;
      totalTimeMs += a.time_ms ?? 0;
    }
  }
  return { correct, totalTimeMs };
}
