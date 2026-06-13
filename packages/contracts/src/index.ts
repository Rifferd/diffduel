export type { paths, components, operations } from './api-types';
import type { components } from './api-types';

export type LoginRequest = components['schemas']['LoginRequest'];
export type RegisterRequest = components['schemas']['RegisterRequest'];
export type TokenResponse = components['schemas']['TokenResponse'];
export type UserMe = components['schemas']['UserMe'];
export type UserUpdate = components['schemas']['UserUpdate'];
export type TopicPublic = components['schemas']['TopicPublic'];
export type UserRole = components['schemas']['UserRole'];
export type TaskPublic = components['schemas']['TaskPublic'];
export type QuizBody = components['schemas']['QuizBody'];
export type TaskType = components['schemas']['TaskType'];
export type AnswerSubmit = components['schemas']['AnswerSubmit'];
export type AnswerPayload = components['schemas']['AnswerPayload'];
export type AnswerResult = components['schemas']['AnswerResult'];

// --- Админка (apps/admin), роутер /admin ---
export type TaskStatus = components['schemas']['TaskStatus'];
export type AdminTask = components['schemas']['AdminTask'];
export type AdminTaskList = components['schemas']['AdminTaskList'];
export type TaskCreate = components['schemas']['TaskCreate'];
export type TaskUpdate = components['schemas']['TaskUpdate'];
export type AdminUser = components['schemas']['AdminUser'];
export type AdminUserList = components['schemas']['AdminUserList'];
export type BanRequest = components['schemas']['BanRequest'];
export type MetricsOverview = components['schemas']['MetricsOverview'];
export type FeatureFlagOut = components['schemas']['FeatureFlagOut'];
export type FeatureFlagUpsert = components['schemas']['FeatureFlagUpsert'];

/** Единый формат ошибки API — контракт фронта (см. conventions.md §Python). */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
