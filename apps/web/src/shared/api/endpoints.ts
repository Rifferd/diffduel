import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  TopicPublic,
  UserMe,
  UserUpdate,
} from '@diffduel/contracts';
import { api } from './client';

export const authApi = {
  register(payload: RegisterRequest): Promise<TokenResponse> {
    return api.request<TokenResponse>('/auth/register', {
      method: 'POST',
      body: payload,
      skipAuthRefresh: true,
    });
  },
  login(payload: LoginRequest): Promise<TokenResponse> {
    return api.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: payload,
      skipAuthRefresh: true,
    });
  },
  logout(): Promise<void> {
    return api.request<void>('/auth/logout', { method: 'POST', skipAuthRefresh: true });
  },
  /** Тихий refresh при старте; skipAuthRefresh, чтобы не зациклить 401-логику. */
  refresh(): Promise<TokenResponse> {
    return api.request<TokenResponse>('/auth/refresh', { method: 'POST', skipAuthRefresh: true });
  },
};

export const meApi = {
  get(): Promise<UserMe> {
    return api.request<UserMe>('/me');
  },
  update(payload: UserUpdate): Promise<UserMe> {
    return api.request<UserMe>('/me', { method: 'PATCH', body: payload });
  },
};

export const topicsApi = {
  list(): Promise<TopicPublic[]> {
    return api.request<TopicPublic[]>('/topics');
  },
};
