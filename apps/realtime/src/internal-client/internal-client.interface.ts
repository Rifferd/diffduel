import type {
  CreateDuelRequest,
  CreateDuelResponse,
  FinishDuelRequest,
  FinishDuelResponse,
} from './internal-client.types';

export const INTERNAL_CLIENT = Symbol('INTERNAL_CLIENT');

/** Abstraction over Core API `/internal/duels*`. Mocked in tests. */
export interface IInternalClient {
  createDuel(req: CreateDuelRequest): Promise<CreateDuelResponse>;
  finishDuel(duelId: string, req: FinishDuelRequest): Promise<FinishDuelResponse>;
}
