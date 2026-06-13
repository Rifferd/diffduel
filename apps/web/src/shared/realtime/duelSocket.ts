import { io, type Socket } from 'socket.io-client';
import type { ClientToServerEvents, ServerToClientEvents } from './duelProtocol';

/**
 * Минимальный интерфейс сокета, от которого зависит `useDuel`.
 *
 * Намеренно уже, чем Socket.IO: только то, что нужно стейт-машине. Это
 * позволяет подменить реальный сокет простым EventEmitter-моком в тестах
 * без socket.io-сервера.
 */
export interface DuelSocketLike {
  on<E extends keyof ServerToClientEvents>(event: E, handler: ServerToClientEvents[E]): void;
  off<E extends keyof ServerToClientEvents>(event: E, handler?: ServerToClientEvents[E]): void;
  /** Системные события транспорта (connect/disconnect/connect_error). */
  on(event: 'connect' | 'disconnect' | 'connect_error', handler: (...args: unknown[]) => void): void;
  off(event: 'connect' | 'disconnect' | 'connect_error', handler?: (...args: unknown[]) => void): void;
  emit<E extends keyof ClientToServerEvents>(
    event: E,
    ...args: Parameters<ClientToServerEvents[E]>
  ): void;
  connect(): void;
  disconnect(): void;
  readonly connected: boolean;
}

export type DuelSocket = Socket<ServerToClientEvents, ClientToServerEvents>;

const DEFAULT_REALTIME_URL = 'ws://localhost:8100';

export interface CreateDuelSocketOptions {
  /** Функция доступа к access JWT (тот же, что хранит auth-стор в памяти). */
  getToken: () => string | null;
  /** Переопределение URL (по умолчанию VITE_REALTIME_URL или ws://localhost:8100). */
  url?: string;
  /** Автоподключение при создании (по умолчанию false — управляет useDuel). */
  autoConnect?: boolean;
}

/**
 * Создаёт типобезопасный Socket.IO-клиент namespace `/duel`.
 *
 * - Авторизация через handshake `auth.token` = access JWT из памяти стора.
 *   Никаких токенов в localStorage.
 * - Встроенный reconnection Socket.IO оставлен включённым; токен берётся
 *   динамически на каждое (пере)подключение через `auth`-функцию.
 */
export function createDuelSocket(options: CreateDuelSocketOptions): DuelSocket {
  const base = (options.url ?? import.meta.env.VITE_REALTIME_URL ?? DEFAULT_REALTIME_URL).replace(
    /\/$/,
    '',
  );

  const socket: DuelSocket = io(`${base}/duel`, {
    autoConnect: options.autoConnect ?? false,
    transports: ['websocket'],
    // Динамический токен: Socket.IO вызывает callback на каждый реконнект.
    auth: (cb: (data: { token: string | null }) => void) => {
      cb({ token: options.getToken() });
    },
  });

  return socket;
}
