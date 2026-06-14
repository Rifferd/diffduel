import { onScopeDispose, ref, shallowRef } from 'vue';
import type { Ref } from 'vue';
import type { DuelSocketLike } from '@/shared/realtime/duelSocket';
import type {
  DuelFinishedEvent,
  DuelMatchedEvent,
  DuelOpponentAnsweredEvent,
  DuelTaskEvent,
  DuelVerdictEvent,
  OpponentInfo,
  SystemErrorEvent,
  SystemReconnectStateEvent,
  TaskBody,
} from '@/shared/realtime/duelProtocol';

/**
 * Фазы дуэли. idle → searching → matched → countdown → playing → finished.
 * reconnecting/error — ортогональные оверлеи, в которые можно попасть из
 * боевых фаз и вернуться (баннер «переподключение» / системная ошибка).
 */
export type DuelPhase =
  | 'idle'
  | 'searching'
  | 'matched'
  | 'countdown'
  | 'playing'
  | 'finished'
  | 'reconnecting'
  | 'error';

/** Снимок статуса соперника по текущей задаче — БЕЗ раскрытия его выбора. */
export interface OpponentStatus {
  /** Соперник ответил на текущую задачу. */
  answered: boolean;
  /** Время ответа соперника, мс (null до ответа). */
  timeMs: number | null;
  /** Верно ли ответил соперник (null до ответа). Выбор не раскрывается. */
  correct: boolean | null;
}

/** Мой вердикт по текущей задаче (есть только после ответа/дедлайна). */
export interface MyVerdict {
  idx: number;
  correct: boolean;
  /** Индекс верной опции — приходит только в duel.verdict. */
  correctOption: number;
  timeMs: number;
}

/** Данные для экрана результата (наполняются на duel.finished). */
export interface DuelResultData {
  /** Идентификатор дуэли — для запроса AI-разбора (Pro). */
  duelId: string | null;
  winnerId: string | null;
  deltas: Record<string, number>;
  elo: Record<string, number>;
  score: { mine: number; opp: number };
  reason: DuelFinishedEvent['reason'];
  topic: string;
  opponent: OpponentInfo | null;
  /** Моё имя пользователя (для шар-карточки). */
  outcome: 'win' | 'loss' | 'draw';
}

export interface UseDuelOptions {
  socket: DuelSocketLike;
  /** Мой user_id — нужен, чтобы прочитать свою дельту/Эло из duel.finished. */
  myUserId: string | null;
  /** Моё имя (для отображения и шар-карточки). */
  myUsername?: string;
  /** Уважать prefers-reduced-motion: без анимации тика таймера. По умолчанию читается из media. */
  reducedMotion?: boolean;
}

export interface UseDuel {
  phase: Ref<DuelPhase>;
  topic: Ref<string | null>;
  opponent: Ref<OpponentInfo | null>;
  tasksCount: Ref<number>;
  /** Обратный отсчёт перед боем (3→2→1), null вне countdown. */
  countdown: Ref<number | null>;
  /** Индекс текущей задачи (0-based), null до первой задачи. */
  taskIndex: Ref<number | null>;
  /** Тело текущей задачи. */
  taskBody: Ref<TaskBody | null>;
  /** Секунд до дедлайна раунда (целое, ≥0). */
  secondsLeft: Ref<number>;
  /** Доля прошедшего времени раунда 0..1 (для tbar). */
  roundProgress: Ref<number>;
  myScore: Ref<number>;
  oppScore: Ref<number>;
  opponentStatus: Ref<OpponentStatus>;
  verdict: Ref<MyVerdict | null>;
  /** Индекс моей выбранной опции по текущей задаче (для подсветки), null до ответа. */
  selected: Ref<number | null>;
  /** Я уже ответил на текущую задачу (ждём соперника/следующую). */
  answered: Ref<boolean>;
  result: Ref<DuelResultData | null>;
  /** Текст системной ошибки (фаза error), null — нет. */
  errorMessage: Ref<string | null>;
  /** Анимация тика отключена (prefers-reduced-motion). */
  reducedMotion: Ref<boolean>;
  joinQueue: (topic: string) => void;
  leaveQueue: () => void;
  answer: (selected: number) => void;
  /** Отписаться и остановить таймеры (вызывается из onScopeDispose автоматически). */
  dispose: () => void;
}

/** Нормализует unix-таймстамп к миллисекундам (сервер может прислать секунды). */
function toMs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

function detectReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Стейт-машина дуэли поверх WS-сокета (см. docs/specs/duels.md).
 * По образцу useTrainingSession: фазы + действия + реактивное состояние,
 * таймеры чистятся на unmount.
 */
export function useDuel(options: UseDuelOptions): UseDuel {
  const { socket, myUserId } = options;

  const phase = ref<DuelPhase>('idle');
  const topic = ref<string | null>(null);
  const opponent = shallowRef<OpponentInfo | null>(null);
  const tasksCount = ref(0);
  const countdown = ref<number | null>(null);
  /** Запоминаем duelId из duel.matched — нужен для AI-разбора на экране результата. */
  let currentDuelId: string | null = null;

  const taskIndex = ref<number | null>(null);
  const taskBody = shallowRef<TaskBody | null>(null);
  const deadlineMs = ref<number>(0);
  const roundDurationMs = ref<number>(30_000);
  const secondsLeft = ref(0);
  const roundProgress = ref(0);

  const myScore = ref(0);
  const oppScore = ref(0);
  const opponentStatus = ref<OpponentStatus>({ answered: false, timeMs: null, correct: null });
  const verdict = ref<MyVerdict | null>(null);
  const selected = ref<number | null>(null);
  const answered = ref(false);

  const result = shallowRef<DuelResultData | null>(null);
  const errorMessage = ref<string | null>(null);
  const reducedMotion = ref<boolean>(options.reducedMotion ?? detectReducedMotion());

  /** Фаза, в которую возвращаемся после reconnecting. */
  let phaseBeforeReconnect: DuelPhase = 'idle';
  let tickHandle: ReturnType<typeof setInterval> | null = null;

  function clearTick(): void {
    if (tickHandle !== null) {
      clearInterval(tickHandle);
      tickHandle = null;
    }
  }

  function recomputeTimer(): void {
    const now = Date.now();
    const remaining = Math.max(0, deadlineMs.value - now);
    secondsLeft.value = Math.ceil(remaining / 1000);
    const dur = roundDurationMs.value || 1;
    roundProgress.value = Math.min(1, Math.max(0, 1 - remaining / dur));
  }

  function startTimer(deadline: number): void {
    clearTick();
    deadlineMs.value = deadline;
    recomputeTimer();
    // При reduced-motion не анимируем плавно — реже обновляем, без визуального тика.
    // В обоих случаях чистая логика secondsLeft через setInterval (RAF не нужен).
    const intervalMs = reducedMotion.value ? 1000 : 250;
    tickHandle = setInterval(() => {
      recomputeTimer();
      if (secondsLeft.value <= 0) clearTick();
    }, intervalMs);
  }

  function resetRoundLocal(): void {
    verdict.value = null;
    selected.value = null;
    answered.value = false;
    opponentStatus.value = { answered: false, timeMs: null, correct: null };
  }

  function computeOutcome(winnerId: string | null, score: { mine: number; opp: number }): DuelResultData['outcome'] {
    if (winnerId === null) return 'draw';
    if (myUserId !== null && winnerId === myUserId) return 'win';
    // Фолбэк по счёту, если myUserId неизвестен.
    if (myUserId === null) {
      if (score.mine > score.opp) return 'win';
      if (score.mine < score.opp) return 'loss';
      return 'draw';
    }
    return 'loss';
  }

  // ---------- server → client handlers ----------

  const onSearching = (): void => {
    // widening отражается через фазу searching; конкретный шаг компонент берёт из события при необходимости.
    if (phase.value === 'idle' || phase.value === 'reconnecting') phase.value = 'searching';
  };

  const onMatched = (e: DuelMatchedEvent): void => {
    currentDuelId = e.duelId;
    topic.value = e.topic;
    opponent.value = e.opponent;
    tasksCount.value = e.tasksCount;
    myScore.value = 0;
    oppScore.value = 0;
    taskIndex.value = null;
    taskBody.value = null;
    resetRoundLocal();
    phase.value = 'matched';
  };

  const onCountdown = (e: { n: number }): void => {
    countdown.value = e.n;
    phase.value = 'countdown';
  };

  const onTask = (e: DuelTaskEvent): void => {
    countdown.value = null;
    taskIndex.value = e.idx;
    taskBody.value = e.body;
    resetRoundLocal();
    phase.value = 'playing';
    const deadline = toMs(e.deadline_ts);
    const now = Date.now();
    // Если сервер не прислал явную длительность — выводим из дедлайна, но не короче 1с.
    roundDurationMs.value = Math.max(1000, deadline - now);
    startTimer(deadline);
  };

  const onOpponentAnswered = (e: DuelOpponentAnsweredEvent): void => {
    if (taskIndex.value !== null && e.idx !== taskIndex.value) return;
    // Только факт/время/верность — НЕ раскрываем выбор соперника.
    opponentStatus.value = { answered: true, timeMs: e.timeMs, correct: e.correct };
  };

  const onVerdict = (e: DuelVerdictEvent): void => {
    if (taskIndex.value !== null && e.idx !== taskIndex.value) return;
    verdict.value = {
      idx: e.idx,
      correct: e.correct,
      correctOption: e.correctOption,
      timeMs: e.timeMs,
    };
    answered.value = true;
    if (e.correct) myScore.value += 1;
  };

  const onFinished = (e: DuelFinishedEvent): void => {
    clearTick();
    myScore.value = e.score.mine;
    oppScore.value = e.score.opp;
    result.value = {
      duelId: currentDuelId,
      winnerId: e.winnerId,
      deltas: e.deltas,
      elo: e.elo,
      score: e.score,
      reason: e.reason,
      topic: topic.value ?? '',
      opponent: opponent.value,
      outcome: computeOutcome(e.winnerId, e.score),
    };
    phase.value = 'finished';
  };

  const onReconnectState = (e: SystemReconnectStateEvent): void => {
    currentDuelId = e.duelId;
    topic.value = topic.value ?? null;
    opponent.value = e.opponent;
    myScore.value = e.score.mine;
    oppScore.value = e.score.opp;
    taskIndex.value = e.idx;

    resetRoundLocal();
    // Восстановить тело текущей задачи и локальный прогресс из снимка.
    if (e.progress.task) taskBody.value = e.progress.task;
    if (e.progress.mine && e.progress.mine.idx === e.idx) {
      selected.value = e.progress.mine.selected;
      answered.value = e.progress.mine.selected !== null;
    }
    if (e.progress.opponent && e.progress.opponent.idx === e.idx) {
      opponentStatus.value = {
        answered: true,
        timeMs: e.progress.opponent.timeMs,
        correct: e.progress.opponent.correct,
      };
    }

    const deadline = toMs(e.deadline_ts);
    roundDurationMs.value = Math.max(1000, deadline - Date.now());
    phase.value = 'playing';
    startTimer(deadline);
  };

  const onSystemError = (e: SystemErrorEvent): void => {
    errorMessage.value = e.message || 'Произошла ошибка соединения.';
    phase.value = 'error';
    clearTick();
  };

  // ---------- transport handlers (reconnect banner) ----------

  const onDisconnect = (): void => {
    // Обрыв во время активной/ожидающей фазы → баннер «переподключение».
    if (phase.value === 'error' || phase.value === 'finished' || phase.value === 'idle') return;
    phaseBeforeReconnect = phase.value;
    phase.value = 'reconnecting';
  };

  const onConnect = (): void => {
    // Вернёмся в боевую фазу; точное состояние придёт через system.reconnect_state.
    if (phase.value === 'reconnecting') phase.value = phaseBeforeReconnect;
  };

  function bind(): void {
    socket.on('queue.searching', onSearching);
    socket.on('duel.matched', onMatched);
    socket.on('duel.countdown', onCountdown);
    socket.on('duel.task', onTask);
    socket.on('duel.opponent_answered', onOpponentAnswered);
    socket.on('duel.verdict', onVerdict);
    socket.on('duel.finished', onFinished);
    socket.on('system.reconnect_state', onReconnectState);
    socket.on('system.error', onSystemError);
    socket.on('disconnect', onDisconnect as (...a: unknown[]) => void);
    socket.on('connect', onConnect as (...a: unknown[]) => void);
    socket.on('connect_error', onDisconnect as (...a: unknown[]) => void);
  }

  function unbind(): void {
    socket.off('queue.searching', onSearching);
    socket.off('duel.matched', onMatched);
    socket.off('duel.countdown', onCountdown);
    socket.off('duel.task', onTask);
    socket.off('duel.opponent_answered', onOpponentAnswered);
    socket.off('duel.verdict', onVerdict);
    socket.off('duel.finished', onFinished);
    socket.off('system.reconnect_state', onReconnectState);
    socket.off('system.error', onSystemError);
    socket.off('disconnect', onDisconnect as (...a: unknown[]) => void);
    socket.off('connect', onConnect as (...a: unknown[]) => void);
    socket.off('connect_error', onDisconnect as (...a: unknown[]) => void);
  }

  // ---------- actions ----------

  function joinQueue(t: string): void {
    errorMessage.value = null;
    topic.value = t;
    phase.value = 'searching';
    if (!socket.connected) socket.connect();
    socket.emit('queue.join', { topic: t });
  }

  function leaveQueue(): void {
    socket.emit('queue.leave');
    phase.value = 'idle';
    clearTick();
  }

  function answer(selectedOption: number): void {
    if (phase.value !== 'playing' || answered.value || taskIndex.value === null) return;
    selected.value = selectedOption;
    answered.value = true; // оптимистично: ждём duel.verdict для correctOption
    socket.emit('duel.answer', { idx: taskIndex.value, selected: selectedOption });
  }

  function dispose(): void {
    clearTick();
    unbind();
  }

  bind();
  onScopeDispose(dispose);

  return {
    phase,
    topic,
    opponent,
    tasksCount,
    countdown,
    taskIndex,
    taskBody,
    secondsLeft,
    roundProgress,
    myScore,
    oppScore,
    opponentStatus,
    verdict,
    selected,
    answered,
    result,
    errorMessage,
    reducedMotion,
    joinQueue,
    leaveQueue,
    answer,
    dispose,
  };
}

/** Форматирует секунды в «M:SS» для моноширинного таймера. */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, '0')}`;
}
