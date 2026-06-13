import type { TokenResponse } from '@diffduel/contracts';
import { toApiError, ApiRequestError } from './errors';

/**
 * Мост к auth-состоянию. Реализуется React-стором в рантайме, но клиент
 * зависит только от интерфейса — это держит его тестируемым без React.
 */
export interface AuthBridge {
  getAccessToken(): string | null;
  setSession(token: TokenResponse): void;
  /** Очистить access-токен в памяти и перевести стор в logout-состояние. */
  clearSession(): void;
  /** Вызывается, когда refresh окончательно провалился (редирект на /login). */
  onAuthFailure(): void;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Не пытаться рефрешить токен (используется самим /auth/refresh). */
  skipAuthRefresh?: boolean;
  signal?: AbortSignal;
}

const DEFAULT_BASE_URL = 'http://localhost:8000';

export class ApiClient {
  private readonly baseURL: string;
  private auth: AuthBridge | null = null;
  /** Общий промис refresh — гарантирует single-flight для конкурентных 401. */
  private refreshing: Promise<boolean> | null = null;

  constructor(baseURL: string = DEFAULT_BASE_URL) {
    this.baseURL = baseURL.replace(/\/$/, '');
  }

  /** Привязка к auth-стору после старта приложения. */
  attachAuth(auth: AuthBridge): void {
    this.auth = auth;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.rawFetch(path, options);

    if (response.status === 401 && !options.skipAuthRefresh) {
      const refreshed = await this.ensureRefreshed();
      if (refreshed) {
        const retry = await this.rawFetch(path, options);
        return this.parse<T>(retry);
      }
      this.auth?.clearSession();
      this.auth?.onAuthFailure();
    }

    return this.parse<T>(response);
  }

  /**
   * Single-flight refresh: одновременные 401-ы ждут один общий промис.
   * Повтор исходного запроса делается ровно один раз вызывающей стороной.
   */
  private ensureRefreshed(): Promise<boolean> {
    if (!this.refreshing) {
      this.refreshing = this.doRefresh().finally(() => {
        this.refreshing = null;
      });
    }
    return this.refreshing;
  }

  private async doRefresh(): Promise<boolean> {
    try {
      const response = await this.rawFetch('/auth/refresh', {
        method: 'POST',
        skipAuthRefresh: true,
      });
      if (!response.ok) return false;
      const token = (await response.json()) as TokenResponse;
      this.auth?.setSession(token);
      return true;
    } catch {
      return false;
    }
  }

  private rawFetch(path: string, options: RequestOptions): Promise<Response> {
    const headers: Record<string, string> = {};
    const token = this.auth?.getAccessToken();
    if (token && !options.skipAuthRefresh) {
      headers.Authorization = `Bearer ${token}`;
    }

    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.body);
    }

    return fetch(`${this.baseURL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body,
      credentials: 'include',
      signal: options.signal,
    });
  }

  private async parse<T>(response: Response): Promise<T> {
    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    const data: unknown = text ? safeJson(text) : undefined;

    if (!response.ok) {
      throw toApiError(response.status, data);
    }
    return data as T;
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export { ApiRequestError };

/** Синглтон клиента для приложения. baseURL — из env. */
export const api = new ApiClient(import.meta.env.VITE_API_URL ?? DEFAULT_BASE_URL);
