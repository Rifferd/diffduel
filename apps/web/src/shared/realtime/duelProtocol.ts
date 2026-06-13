/**
 * Контракт WebSocket-протокола дуэлей (namespace `/duel`).
 *
 * Источник истины — docs/specs/duels.md §WebSocket-протокол. Формы и имена
 * событий здесь обязаны совпадать с сервером (Realtime, NestJS). Меняется
 * только синхронно со спекой.
 */

// ---------- client → server ----------

export interface QueueJoinPayload {
  topic: string;
}

/** {idx, selected} — время меряет сервер от отправки duel.task. */
export interface DuelAnswerPayload {
  idx: number;
  selected: number;
}

export interface ClientToServerEvents {
  'queue.join': (payload: QueueJoinPayload) => void;
  'queue.leave': () => void;
  'duel.answer': (payload: DuelAnswerPayload) => void;
}

// ---------- server → client ----------

/** Соперник в матче/реконнекте — без чувствительных данных. */
export interface OpponentInfo {
  username: string;
  elo: number;
}

export interface QueueSearchingEvent {
  /** Текущее расширение окна поиска (шаг), целое; растёт со временем. */
  widening: number;
}

export interface DuelMatchedEvent {
  duelId: string;
  topic: string;
  opponent: OpponentInfo;
  tasksCount: number;
}

export interface DuelCountdownEvent {
  n: 3 | 2 | 1;
}

/** Задача без эталона — body как в соло-тренировке. */
export interface DuelTaskEvent {
  idx: number;
  body: TaskBody;
  /** Unix-время дедлайна (мс или с — нормализуем на клиенте). */
  deadline_ts: number;
}

/** Соперник ответил — без раскрытия его выбора. */
export interface DuelOpponentAnsweredEvent {
  idx: number;
  timeMs: number;
  correct: boolean;
}

/** Вердикт по моему ответу — только автору; correctOption приходит только тут. */
export interface DuelVerdictEvent {
  idx: number;
  correct: boolean;
  correctOption: number;
  timeMs: number;
}

export interface DuelScore {
  mine: number;
  opp: number;
}

export interface DuelFinishedEvent {
  winnerId: string | null;
  /** Дельты Эло по player_id. */
  deltas: Record<string, number>;
  /** Итоговый рейтинг по player_id. */
  elo: Record<string, number>;
  score: DuelScore;
  reason: 'completed' | 'opponent_left' | 'aborted';
}

/** Снимок состояния для восстановления после обрыва соединения. */
export interface SystemReconnectStateEvent {
  duelId: string;
  idx: number;
  deadline_ts: number;
  /** Снимок прогресса обеих сторон (формы зависят от сервера). */
  progress: ReconnectProgress;
  opponent: OpponentInfo;
  score: DuelScore;
}

/** Прогресс из reconnect_state: ответы по задачам обеих сторон. */
export interface ReconnectProgress {
  /** Текущая задача (если активна) — чтобы перерисовать вопрос. */
  task?: TaskBody | null;
  /** Мой ответ на текущую задачу (если уже дан). */
  mine?: { idx: number; selected: number | null } | null;
  /** Статус соперника по текущей задаче (если уже ответил). */
  opponent?: { idx: number; timeMs: number; correct: boolean } | null;
}

export interface SystemErrorEvent {
  code: string;
  message: string;
}

/** Тело задачи (quiz): тот же контракт, что и TaskPublic.body в соло. */
export interface TaskBody {
  question: string;
  options: string[];
  code?: string | null;
  language?: string | null;
  tags?: string[];
}

export interface ServerToClientEvents {
  'queue.searching': (e: QueueSearchingEvent) => void;
  'duel.matched': (e: DuelMatchedEvent) => void;
  'duel.countdown': (e: DuelCountdownEvent) => void;
  'duel.task': (e: DuelTaskEvent) => void;
  'duel.opponent_answered': (e: DuelOpponentAnsweredEvent) => void;
  'duel.verdict': (e: DuelVerdictEvent) => void;
  'duel.finished': (e: DuelFinishedEvent) => void;
  'system.reconnect_state': (e: SystemReconnectStateEvent) => void;
  'system.error': (e: SystemErrorEvent) => void;
}
