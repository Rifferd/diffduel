import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { effectScope } from 'vue';
import { useDuel, formatClock } from './useDuel';
import type { UseDuel } from './useDuel';
import type { DuelSocketLike } from '@/shared/realtime/duelSocket';
import type { ServerToClientEvents } from '@/shared/realtime/duelProtocol';

/** Простой EventEmitter-образный мок сокета для эмуляции сервера. */
class MockSocket implements DuelSocketLike {
  private handlers = new Map<string, Set<(...args: unknown[]) => void>>();
  connected = false;
  /** Записанные исходящие emit'ы для проверок. */
  sent: Array<{ event: string; args: unknown[] }> = [];

  on(event: string, handler: (...args: unknown[]) => void): void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
  }
  off(event: string, handler?: (...args: unknown[]) => void): void {
    if (!handler) {
      this.handlers.delete(event);
      return;
    }
    this.handlers.get(event)?.delete(handler);
  }
  emit(event: string, ...args: unknown[]): void {
    this.sent.push({ event, args });
  }
  connect(): void {
    this.connected = true;
  }
  disconnect(): void {
    this.connected = false;
  }

  /** Эмулирует серверное событие. */
  server<E extends keyof ServerToClientEvents>(
    event: E,
    ...args: Parameters<ServerToClientEvents[E]>
  ): void {
    this.handlers.get(event as string)?.forEach((h) => h(...(args as unknown[])));
  }
  /** Эмулирует транспортное событие (disconnect/connect). */
  transport(event: 'connect' | 'disconnect' | 'connect_error'): void {
    this.handlers.get(event)?.forEach((h) => h());
  }
}

function setup(socket: MockSocket, myUserId = 'me'): { duel: UseDuel; stop: () => void } {
  const scope = effectScope();
  const duel = scope.run(() =>
    useDuel({ socket, myUserId, myUsername: 'anton_dev', reducedMotion: true }),
  )!;
  return { duel, stop: () => scope.stop() };
}

describe('useDuel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-13T00:00:00Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('searching → matched → countdown → playing', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);

    expect(duel.phase.value).toBe('idle');
    duel.joinQueue('sql');
    expect(duel.phase.value).toBe('searching');
    expect(socket.sent).toContainEqual({ event: 'queue.join', args: [{ topic: 'sql' }] });
    expect(socket.connected).toBe(true);

    socket.server('queue.searching', { widening: 1 });
    expect(duel.phase.value).toBe('searching');

    socket.server('duel.matched', {
      duelId: 'd1',
      topic: 'sql',
      opponent: { username: 'sql_ninja', elo: 1507 },
      tasksCount: 5,
    });
    expect(duel.phase.value).toBe('matched');
    expect(duel.opponent.value?.username).toBe('sql_ninja');
    expect(duel.tasksCount.value).toBe(5);

    socket.server('duel.countdown', { n: 3 });
    expect(duel.phase.value).toBe('countdown');
    expect(duel.countdown.value).toBe(3);

    socket.server('duel.task', {
      idx: 0,
      body: { question: 'Q1', options: ['a', 'b'] },
      deadline_ts: Date.now() + 30_000,
    });
    expect(duel.phase.value).toBe('playing');
    expect(duel.countdown.value).toBeNull();
    expect(duel.taskBody.value?.question).toBe('Q1');
    stop();
  });

  it('duel.task стартует таймер обратного отсчёта раунда', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);
    duel.joinQueue('sql');

    socket.server('duel.task', {
      idx: 0,
      body: { question: 'Q', options: ['a', 'b'] },
      deadline_ts: Date.now() + 30_000,
    });
    expect(duel.secondsLeft.value).toBe(30);
    expect(duel.roundProgress.value).toBeCloseTo(0, 2);

    vi.advanceTimersByTime(10_000);
    expect(duel.secondsLeft.value).toBe(20);
    expect(duel.roundProgress.value).toBeCloseTo(1 / 3, 1);

    // Таймер останавливается на нуле и не уходит в минус.
    vi.advanceTimersByTime(30_000);
    expect(duel.secondsLeft.value).toBe(0);
    expect(duel.roundProgress.value).toBe(1);
    stop();
  });

  it('answer отправляет duel.answer, verdict фиксирует результат и счёт', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);
    duel.joinQueue('sql');
    socket.server('duel.task', {
      idx: 0,
      body: { question: 'Q', options: ['a', 'b', 'c'] },
      deadline_ts: Date.now() + 30_000,
    });

    duel.answer(2);
    expect(socket.sent).toContainEqual({ event: 'duel.answer', args: [{ idx: 0, selected: 2 }] });
    expect(duel.selected.value).toBe(2);
    expect(duel.answered.value).toBe(true);

    // Повторный ответ игнорируется.
    duel.answer(1);
    expect(socket.sent.filter((s) => s.event === 'duel.answer')).toHaveLength(1);

    socket.server('duel.verdict', { idx: 0, correct: true, correctOption: 2, timeMs: 5100 });
    expect(duel.verdict.value?.correct).toBe(true);
    expect(duel.verdict.value?.correctOption).toBe(2);
    expect(duel.myScore.value).toBe(1);
    stop();
  });

  it('opponent_answered обновляет статус соперника без раскрытия его выбора', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);
    duel.joinQueue('sql');
    socket.server('duel.task', {
      idx: 0,
      body: { question: 'Q', options: ['a', 'b'] },
      deadline_ts: Date.now() + 30_000,
    });

    socket.server('duel.opponent_answered', { idx: 0, timeMs: 7400, correct: true });
    const status = duel.opponentStatus.value;
    expect(status.answered).toBe(true);
    expect(status.timeMs).toBe(7400);
    expect(status.correct).toBe(true);
    // Никакого поля с выбором соперника не существует в типе/значении.
    expect(Object.keys(status)).toEqual(['answered', 'timeMs', 'correct']);
    expect(Object.keys(status)).not.toContain('selected');
    stop();
  });

  it('duel.finished наполняет результат (победа по winnerId)', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket, 'me');
    duel.joinQueue('sql');
    socket.server('duel.matched', {
      duelId: 'd1',
      topic: 'sql',
      opponent: { username: 'sql_ninja', elo: 1507 },
      tasksCount: 5,
    });

    socket.server('duel.finished', {
      winnerId: 'me',
      deltas: { me: 24, opp: -18 },
      elo: { me: 1506, opp: 1489 },
      score: { mine: 4, opp: 2 },
      reason: 'completed',
    });
    expect(duel.phase.value).toBe('finished');
    const r = duel.result.value!;
    expect(r.outcome).toBe('win');
    expect(r.deltas.me).toBe(24);
    expect(r.score).toEqual({ mine: 4, opp: 2 });
    expect(r.topic).toBe('sql');
    expect(r.opponent?.username).toBe('sql_ninja');
    stop();
  });

  it('system.reconnect_state восстанавливает состояние раунда', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);
    duel.joinQueue('sql');

    // Имитация обрыва: баннер переподключения.
    socket.server('duel.task', {
      idx: 0,
      body: { question: 'Q', options: ['a', 'b'] },
      deadline_ts: Date.now() + 30_000,
    });
    socket.transport('disconnect');
    expect(duel.phase.value).toBe('reconnecting');

    socket.transport('connect');
    socket.server('system.reconnect_state', {
      duelId: 'd1',
      idx: 2,
      deadline_ts: Date.now() + 18_000,
      progress: {
        task: { question: 'Q3', options: ['x', 'y', 'z'] },
        mine: { idx: 2, selected: 1 },
        opponent: { idx: 2, timeMs: 9100, correct: false },
      },
      opponent: { username: 'sql_ninja', elo: 1507 },
      score: { mine: 1, opp: 1 },
    });

    expect(duel.phase.value).toBe('playing');
    expect(duel.taskIndex.value).toBe(2);
    expect(duel.taskBody.value?.question).toBe('Q3');
    expect(duel.myScore.value).toBe(1);
    expect(duel.oppScore.value).toBe(1);
    expect(duel.selected.value).toBe(1);
    expect(duel.answered.value).toBe(true);
    expect(duel.opponentStatus.value.answered).toBe(true);
    expect(duel.opponentStatus.value.correct).toBe(false);
    expect(duel.secondsLeft.value).toBe(18);
    stop();
  });

  it('system.error переводит в фазу error с сообщением', () => {
    const socket = new MockSocket();
    const { duel, stop } = setup(socket);
    duel.joinQueue('sql');
    socket.server('system.error', { code: 'duel_not_found', message: 'Дуэль не найдена' });
    expect(duel.phase.value).toBe('error');
    expect(duel.errorMessage.value).toBe('Дуэль не найдена');
    stop();
  });

  it('formatClock форматирует моноширинное время', () => {
    expect(formatClock(0)).toBe('0:00');
    expect(formatClock(7)).toBe('0:07');
    expect(formatClock(17)).toBe('0:17');
    expect(formatClock(90)).toBe('1:30');
  });
});
