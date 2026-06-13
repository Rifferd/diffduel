import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { LoginRequest, TokenResponse, UserMe } from '@diffduel/contracts';
import { api } from '@/shared/api/client';
import { authApi, meApi } from '@/shared/api/endpoints';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  status: AuthStatus;
  user: UserMe | null;
  /** Имеет ли пользователь доступ в админку (moderator/admin). */
  isAdminRole: boolean;
  login(payload: LoginRequest): Promise<void>;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const ADMIN_ROLES = new Set(['moderator', 'admin']);

export function AuthProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<UserMe | null>(null);
  /** Access-токен живёт ТОЛЬКО в памяти, никакого localStorage. */
  const tokenRef = useRef<string | null>(null);

  const clearSession = useCallback(() => {
    tokenRef.current = null;
    setUser(null);
    setStatus('anonymous');
  }, []);

  const setSession = useCallback((token: TokenResponse) => {
    tokenRef.current = token.access_token;
  }, []);

  // Привязать стор к API-клиенту как AuthBridge до первого запроса.
  useEffect(() => {
    api.attachAuth({
      getAccessToken: () => tokenRef.current,
      setSession,
      clearSession,
      onAuthFailure: clearSession,
    });
  }, [setSession, clearSession]);

  // Тихая попытка восстановить сессию по httpOnly refresh-cookie.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const token = await authApi.refresh();
        setSession(token);
        const me = await meApi.get();
        if (cancelled) return;
        setUser(me);
        setStatus('authenticated');
      } catch {
        if (!cancelled) clearSession();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setSession, clearSession]);

  const login = useCallback(
    async (payload: LoginRequest) => {
      const token = await authApi.login(payload);
      setSession(token);
      const me = await meApi.get();
      setUser(me);
      setStatus('authenticated');
    },
    [setSession],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isAdminRole: user !== null && ADMIN_ROLES.has(user.role),
      login,
      logout,
    }),
    [status, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- хук соседствует с провайдером намеренно
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
