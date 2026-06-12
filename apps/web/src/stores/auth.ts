import { defineStore } from 'pinia';
import type { LoginRequest, RegisterRequest, TokenResponse, UserMe } from '@diffduel/contracts';
import { api } from '@/shared/api/client';
import { authApi, meApi } from '@/shared/api/endpoints';

interface AuthState {
  /** Access-токен живёт ТОЛЬКО в памяти, никакого localStorage. */
  accessToken: string | null;
  user: UserMe | null;
  /** Пока не завершён стартовый тихий refresh — роутер ждёт. */
  ready: boolean;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: null,
    user: null,
    ready: false,
  }),
  getters: {
    isAuthenticated: (state): boolean => state.accessToken !== null,
  },
  actions: {
    setSession(token: TokenResponse): void {
      this.accessToken = token.access_token;
    },
    clearSession(): void {
      this.accessToken = null;
      this.user = null;
    },
    onAuthFailure(): void {
      this.clearSession();
      // Жёсткий редирект через window, чтобы не тащить роутер в стор/клиент.
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    },

    /** Тихая попытка восстановить сессию по httpOnly refresh-cookie. */
    async bootstrap(): Promise<void> {
      try {
        const token = await authApi.refresh();
        this.setSession(token);
        await this.fetchMe();
      } catch {
        this.clearSession();
      } finally {
        this.ready = true;
      }
    },

    async login(payload: LoginRequest): Promise<void> {
      const token = await authApi.login(payload);
      this.setSession(token);
      await this.fetchMe();
    },

    async register(payload: RegisterRequest): Promise<void> {
      const token = await authApi.register(payload);
      this.setSession(token);
      await this.fetchMe();
    },

    async logout(): Promise<void> {
      try {
        await authApi.logout();
      } finally {
        this.clearSession();
      }
    },

    async fetchMe(): Promise<UserMe> {
      const user = await meApi.get();
      this.user = user;
      return user;
    },
  },
});

/** Привязывает auth-стор к API-клиенту как AuthBridge. */
export function bindAuthBridge(): void {
  const store = useAuthStore();
  api.attachAuth({
    getAccessToken: () => store.accessToken,
    setSession: (token) => store.setSession(token),
    clearSession: () => store.clearSession(),
    onAuthFailure: () => store.onAuthFailure(),
  });
}
