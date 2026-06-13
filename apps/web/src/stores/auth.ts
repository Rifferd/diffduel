import { defineStore } from 'pinia';
import type { LoginRequest, RegisterRequest, TokenResponse, UserMe } from '@diffduel/contracts';
import { api } from '@/shared/api/client';
import { authApi, meApi } from '@/shared/api/endpoints';
import type { RegisterResponse, VerifyLinkResponse } from '@/shared/api/endpoints';

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

    /**
     * Регистрация. Режим OFF (verification_required:false) — авто-логин.
     * Режим ON (true) — токенов нет, сессия НЕ создаётся; ветвление наверху.
     */
    async register(payload: RegisterRequest): Promise<RegisterResponse> {
      const res = await authApi.register(payload);
      if (res.verification_required === false) {
        this.setSession(res);
        await this.fetchMe();
      }
      return res;
    },

    /** Подтверждение кодом — при успехе логинит. */
    async verifyEmail(email: string, code: string): Promise<void> {
      const token = await authApi.verifyEmail({ email, code });
      this.setSession(token);
      await this.fetchMe();
    },

    /** Подтверждение по ссылке. logged_in:true → логинит; иначе сессия не создаётся. */
    async verifyLink(token: string): Promise<VerifyLinkResponse> {
      const res = await authApi.verifyLink({ token });
      if (res.logged_in) {
        this.setSession(res);
        await this.fetchMe();
      }
      return res;
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
