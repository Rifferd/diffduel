import type {
  AnswerResult,
  AnswerSubmit,
  components,
  LoginRequest,
  RegisterRequest,
  TaskPublic,
  TokenResponse,
  TopicPublic,
  UserMe,
  UserUpdate,
} from '@diffduel/contracts';

export type LeaderboardEntry = components['schemas']['LeaderboardEntry'];
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

export interface PublicLeaderboardParams {
  scope?: 'global' | 'weekly';
  limit?: number;
}

export const leaderboardApi = {
  /** Публичный лидерборд (без auth) — используется лендингом. */
  public({ scope, limit }: PublicLeaderboardParams = {}): Promise<LeaderboardEntry[]> {
    const params = new URLSearchParams();
    if (scope !== undefined) params.set('scope', scope);
    if (limit !== undefined) params.set('limit', String(limit));
    const qs = params.toString();
    return api.request<LeaderboardEntry[]>(`/leaderboard${qs ? `?${qs}` : ''}`, {
      skipAuthRefresh: true,
    });
  },
};

export const topicsApi = {
  list(): Promise<TopicPublic[]> {
    return api.request<TopicPublic[]>('/topics');
  },
};

export interface TrainingTasksParams {
  topic: string;
  difficulty?: number;
  limit?: number;
  signal?: AbortSignal;
}

export const tasksApi = {
  training({ topic, difficulty, limit, signal }: TrainingTasksParams): Promise<TaskPublic[]> {
    const params = new URLSearchParams({ topic });
    if (difficulty !== undefined) params.set('difficulty', String(difficulty));
    if (limit !== undefined) params.set('limit', String(limit));
    return api.request<TaskPublic[]>(`/tasks/training?${params.toString()}`, { signal });
  },
  submitAnswer(payload: AnswerSubmit): Promise<AnswerResult> {
    return api.request<AnswerResult>('/answers', { method: 'POST', body: payload });
  },
};
