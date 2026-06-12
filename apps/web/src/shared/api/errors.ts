import type { ApiError } from '@diffduel/contracts';

/** Ошибка API в едином формате `{ error: { code, message, details } }`. */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isApiErrorShape(value: unknown): value is ApiError {
  if (typeof value !== 'object' || value === null) return false;
  const err = (value as { error?: unknown }).error;
  if (typeof err !== 'object' || err === null) return false;
  return typeof (err as { code?: unknown }).code === 'string';
}

/** Строит ApiRequestError из тела ответа, мягко переживая нестандартные ответы. */
export function toApiError(status: number, body: unknown): ApiRequestError {
  if (isApiErrorShape(body)) {
    return new ApiRequestError(status, body.error.code, body.error.message, body.error.details);
  }
  return new ApiRequestError(status, 'unknown_error', 'Что-то пошло не так. Попробуйте позже.');
}
