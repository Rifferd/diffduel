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

/** Единый формат ошибки API — контракт фронта (см. conventions.md §Python). */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
