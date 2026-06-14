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

// --- Релиз 2: Pro, статистика, дневной челлендж, AI-разбор ---
export type UserProfile = components['schemas']['UserProfile'];
export type UserStats = components['schemas']['UserStats'];
export type TopicAccuracy = components['schemas']['TopicAccuracy'];
export type TopicRating = components['schemas']['TopicRating'];
export type DailyTask = components['schemas']['DailyTask'];
export type DailyAnswerSubmit = components['schemas']['DailyAnswerSubmit'];
export type DailyAnswerResult = components['schemas']['DailyAnswerResult'];
export type DailyLeaderboardEntry = components['schemas']['DailyLeaderboardEntry'];
export type DailyMyPosition = components['schemas']['DailyMyPosition'];
export type AiReviewResponse = components['schemas']['AiReviewResponse'];
export type AiReviewStatus = components['schemas']['AiReviewStatus'];
export type GrantProRequest = components['schemas']['GrantProRequest'];
export type ProStatus = components['schemas']['ProStatus'];

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

// --- Релиз 3: турниры ---
export type TournamentStatus = components['schemas']['TournamentStatus'];
export type TournamentSummary = components['schemas']['TournamentSummary'];
export type TournamentDetail = components['schemas']['TournamentDetail'];
export type TournamentLeaderboardEntry = components['schemas']['TournamentLeaderboardEntry'];
export type TournamentTasks = components['schemas']['TournamentTasks'];
export type EnterResult = components['schemas']['EnterResult'];
export type TournamentAnswerSubmit = components['schemas']['TournamentAnswerSubmit'];
export type TournamentAnswerResult = components['schemas']['TournamentAnswerResult'];
export type AdminTournament = components['schemas']['AdminTournament'];
export type TournamentCreate = components['schemas']['TournamentCreate'];
export type TournamentUpdate = components['schemas']['TournamentUpdate'];
export type GrantEntryRequest = components['schemas']['GrantEntryRequest'];

/** Единый формат ошибки API — контракт фронта (см. conventions.md §Python). */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
