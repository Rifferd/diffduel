import type {
  AiReviewResponse,
  AnswerResult,
  AnswerSubmit,
  components,
  DailyAnswerResult,
  DailyAnswerSubmit,
  DailyLeaderboardEntry,
  DailyMyPosition,
  DailyTask,
  EnterResult,
  LoginRequest,
  RegisterRequest,
  TaskPublic,
  TokenResponse,
  TopicPublic,
  TournamentAnswerResult,
  TournamentAnswerSubmit,
  TournamentDetail,
  TournamentStatus,
  TournamentSummary,
  TournamentTasks,
  UserMe,
  UserStats,
  UserUpdate,
} from '@diffduel/contracts';

export type LeaderboardEntry = components['schemas']['LeaderboardEntry'];
import { api } from './client';

/**
 * Контракт подтверждения email (docs/specs/email-verification.md).
 * TODO(contracts): убрать локальные типы и перегенерить `@diffduel/contracts`
 * (`npm exec -y pnpm@9 -- -C packages/contracts generate` против localhost:8000),
 * как только API-агент опубликует эндпоинты verify-email/verify-link/resend-code
 * и обновит RegisterRequest/register-response в OpenAPI.
 */

/** Ответ register: либо авто-логин (OFF), либо требование подтверждения (ON). */
export type RegisterResponse =
  | ({ verification_required: false } & TokenResponse)
  | { verification_required: true };

export interface VerifyEmailRequest {
  email: string;
  code: string;
}

export interface VerifyLinkRequest {
  token: string;
}

/** Ответ verify-link: то же устройство (logged_in+токены) или другое (без логина). */
export type VerifyLinkResponse =
  | ({ logged_in: true } & TokenResponse)
  | { logged_in: false; code?: string };

export const authApi = {
  register(payload: RegisterRequest): Promise<RegisterResponse> {
    return api.request<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: payload,
      skipAuthRefresh: true,
    });
  },
  verifyEmail(payload: VerifyEmailRequest): Promise<TokenResponse> {
    return api.request<TokenResponse>('/auth/verify-email', {
      method: 'POST',
      body: payload,
      skipAuthRefresh: true,
    });
  },
  verifyLink(payload: VerifyLinkRequest): Promise<VerifyLinkResponse> {
    return api.request<VerifyLinkResponse>('/auth/verify-link', {
      method: 'POST',
      body: payload,
      skipAuthRefresh: true,
    });
  },
  resendCode(email: string): Promise<void> {
    return api.request<void>('/auth/resend-code', {
      method: 'POST',
      body: { email },
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
  /** Расширенная статистика профиля — Pro-функция (402 pro_required без Pro). */
  stats(period?: number): Promise<UserStats> {
    const qs = period !== undefined ? `?period=${period}` : '';
    return api.request<UserStats>(`/me/stats${qs}`);
  },
};

/** Дневной челлендж (не Pro-гейтед). */
export const dailyApi = {
  get(): Promise<DailyTask> {
    return api.request<DailyTask>('/daily');
  },
  answer(payload: DailyAnswerSubmit): Promise<DailyAnswerResult> {
    return api.request<DailyAnswerResult>('/daily/answer', { method: 'POST', body: payload });
  },
  leaderboard(limit?: number): Promise<DailyLeaderboardEntry[]> {
    const qs = limit !== undefined ? `?limit=${limit}` : '';
    return api.request<DailyLeaderboardEntry[]>(`/daily/leaderboard${qs}`);
  },
  me(): Promise<DailyMyPosition> {
    return api.request<DailyMyPosition>('/daily/me');
  },
};

/** AI-разбор дуэли — Pro-функция (POST даёт 402 pro_required без Pro). */
export const aiReviewApi = {
  start(duelId: string): Promise<AiReviewResponse> {
    return api.request<AiReviewResponse>(`/ai/review/${duelId}`, { method: 'POST' });
  },
  get(duelId: string): Promise<AiReviewResponse> {
    return api.request<AiReviewResponse>(`/ai/review/${duelId}`);
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

export const tournamentsApi = {
  /** Список турниров; необязательный фильтр по статусу. Публичный (без auth). */
  list(status?: TournamentStatus): Promise<TournamentSummary[]> {
    const qs = status ? `?status=${status}` : '';
    return api.request<TournamentSummary[]>(`/tournaments${qs}`, { skipAuthRefresh: true });
  },
  /** Детали + лидерборд. Публичный. */
  detail(id: string): Promise<TournamentDetail> {
    return api.request<TournamentDetail>(`/tournaments/${id}`, { skipAuthRefresh: true });
  },
  /** Вход в турнир (auth). 402 entry_payment_unavailable — платёж недоступен. */
  enter(id: string): Promise<EnterResult> {
    return api.request<EnterResult>(`/tournaments/${id}/enter`, { method: 'POST' });
  },
  /** Задачи турнира без эталонов (auth, участник, active). */
  tasks(id: string): Promise<TournamentTasks> {
    return api.request<TournamentTasks>(`/tournaments/${id}/tasks`);
  },
  submitAnswer(id: string, payload: TournamentAnswerSubmit): Promise<TournamentAnswerResult> {
    return api.request<TournamentAnswerResult>(`/tournaments/${id}/answer`, {
      method: 'POST',
      body: payload,
    });
  },
};
