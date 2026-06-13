/**
 * Lua scripts for atomic matchmaking operations. Pairing must be atomic so two
 * service instances (or two ticks) cannot claim the same player (TZ §11 п.10).
 */

/**
 * Atomically pair two candidates.
 * KEYS[1] = mm:{topic} (ZSET), KEYS[2] = mm:meta:{topic} (HASH)
 * ARGV[1] = userA, ARGV[2] = userB
 * Returns 1 if BOTH were present and got removed, else 0 (and removes nothing).
 */
export const PAIR_SCRIPT = `
local a = ARGV[1]
local b = ARGV[2]
local sa = redis.call('ZSCORE', KEYS[1], a)
local sb = redis.call('ZSCORE', KEYS[1], b)
if not sa or not sb then
  return 0
end
redis.call('ZREM', KEYS[1], a, b)
redis.call('HDEL', KEYS[2], a, b)
return 1
`;

/**
 * Atomically remove a single user from a topic queue.
 * KEYS[1] = mm:{topic} (ZSET), KEYS[2] = mm:meta:{topic} (HASH)
 * ARGV[1] = userId
 * Returns 1 if the user was in the queue, else 0.
 */
export const LEAVE_SCRIPT = `
local u = ARGV[1]
local existed = redis.call('ZREM', KEYS[1], u)
redis.call('HDEL', KEYS[2], u)
return existed
`;
