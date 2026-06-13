import type {
  AdminTask,
  AdminTaskList,
  AdminUser,
  AdminUserList,
  BanRequest,
  FeatureFlagOut,
  FeatureFlagUpsert,
  LoginRequest,
  MetricsOverview,
  TaskCreate,
  TaskStatus,
  TaskUpdate,
  TokenResponse,
  TopicPublic,
  UserMe,
} from '@diffduel/contracts';
import { api } from './client';

export const authApi = {
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
};

export const topicsApi = {
  list(): Promise<TopicPublic[]> {
    return api.request<TopicPublic[]>('/topics');
  },
};

export const metricsApi = {
  overview(): Promise<MetricsOverview> {
    return api.request<MetricsOverview>('/admin/metrics/overview');
  },
};

export interface AdminTasksParams {
  status?: TaskStatus | '';
  topic?: string;
  page?: number;
  pageSize?: number;
}

export const adminTasksApi = {
  list({ status, topic, page, pageSize }: AdminTasksParams = {}): Promise<AdminTaskList> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (topic) params.set('topic', topic);
    if (page !== undefined) params.set('page', String(page));
    if (pageSize !== undefined) params.set('page_size', String(pageSize));
    const qs = params.toString();
    return api.request<AdminTaskList>(`/admin/tasks${qs ? `?${qs}` : ''}`);
  },
  create(payload: TaskCreate): Promise<AdminTask> {
    return api.request<AdminTask>('/admin/tasks', { method: 'POST', body: payload });
  },
  update(id: string, payload: TaskUpdate): Promise<AdminTask> {
    return api.request<AdminTask>(`/admin/tasks/${id}`, { method: 'PATCH', body: payload });
  },
  publish(id: string): Promise<AdminTask> {
    return api.request<AdminTask>(`/admin/tasks/${id}/publish`, { method: 'POST' });
  },
  reject(id: string): Promise<AdminTask> {
    return api.request<AdminTask>(`/admin/tasks/${id}/reject`, { method: 'POST' });
  },
};

export interface AdminUsersParams {
  q?: string;
  page?: number;
  pageSize?: number;
}

export const adminUsersApi = {
  list({ q, page, pageSize }: AdminUsersParams = {}): Promise<AdminUserList> {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (page !== undefined) params.set('page', String(page));
    if (pageSize !== undefined) params.set('page_size', String(pageSize));
    const qs = params.toString();
    return api.request<AdminUserList>(`/admin/users${qs ? `?${qs}` : ''}`);
  },
  ban(id: string, payload: BanRequest): Promise<AdminUser> {
    return api.request<AdminUser>(`/admin/users/${id}/ban`, { method: 'POST', body: payload });
  },
  unban(id: string): Promise<AdminUser> {
    return api.request<AdminUser>(`/admin/users/${id}/unban`, { method: 'POST' });
  },
};

export const flagsApi = {
  list(): Promise<FeatureFlagOut[]> {
    return api.request<FeatureFlagOut[]>('/admin/feature-flags');
  },
  upsert(key: string, payload: FeatureFlagUpsert): Promise<FeatureFlagOut> {
    return api.request<FeatureFlagOut>(`/admin/feature-flags/${key}`, {
      method: 'PUT',
      body: payload,
    });
  },
};
