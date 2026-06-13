/**
 * Redis key builders. Layout is fixed by docs/specs/duels.md ("Redis").
 * Centralised here so the contract lives in exactly one place.
 */
export const RedisKeys = {
  mmQueue: (topic: string): string => `mm:${topic}`,
  mmMeta: (topic: string): string => `mm:meta:${topic}`,
  duel: (duelId: string): string => `duel:${duelId}`,
  userActiveDuel: (userId: string): string => `user:active-duel:${userId}`,

  // Service-local (not in spec): elo cache + join rate limit.
  eloCache: (topic: string): string => `elo:${topic}`,
  joinRate: (userId: string): string => `mm:rate:${userId}`,
} as const;

/** Socket.IO room names. */
export const Rooms = {
  user: (userId: string): string => `user:${userId}`,
  duel: (duelId: string): string => `duel:${duelId}`,
} as const;

export const DEFAULT_ELO = 1200;
/** TTL for duel:{id} and user:active-duel:{uid} — 2h per spec. */
export const DUEL_TTL_SECONDS = 2 * 60 * 60;
