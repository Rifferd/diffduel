/**
 * Atomically record an answer in the duel:{id} HASH `progress` field.
 *
 * Reading-modifying-writing progress from Node is racy: two answers (possibly
 * on different service instances) can both read the old progress and clobber
 * each other. This script does the read, validation, append and both-answered
 * check inside a single Redis call.
 *
 * KEYS[1] = duel:{id}
 * ARGV[1] = userId
 * ARGV[2] = expectedIdx (number)
 * ARGV[3] = record JSON (AnswerProgressRecord)
 * ARGV[4] = playerA
 * ARGV[5] = playerB
 *
 * Returns a 2-element array: { code, bothAnswered }
 *   code: 'ok' | 'duel_not_running' | 'wrong_task' | 'already_answered'
 *   bothAnswered: 1 if both players now have an answer for expectedIdx, else 0
 */
export const RECORD_ANSWER_SCRIPT = `
local raw = redis.call('HGET', KEYS[1], 'progress')
local status = redis.call('HGET', KEYS[1], 'status')
local curIdx = redis.call('HGET', KEYS[1], 'idx')
if not raw or status ~= 'running' then
  return { 'duel_not_running', 0 }
end
local expectedIdx = tonumber(ARGV[2])
if tonumber(curIdx) ~= expectedIdx then
  return { 'wrong_task', 0 }
end

local progress = cjson.decode(raw)
local user = ARGV[1]
local list = progress[user]
if list == nil then
  list = {}
  progress[user] = list
end
for _, a in ipairs(list) do
  if a.idx == expectedIdx then
    return { 'already_answered', 0 }
  end
end

local record = cjson.decode(ARGV[3])
table.insert(list, record)
-- cjson encodes an empty Lua table as an object; force array semantics by
-- always re-encoding the whole progress map (lists are non-empty here).
redis.call('HSET', KEYS[1], 'progress', cjson.encode(progress))

local function answered(uid)
  local l = progress[uid]
  if l == nil then return false end
  for _, a in ipairs(l) do
    if a.idx == expectedIdx then return true end
  end
  return false
end

local both = 0
if answered(ARGV[4]) and answered(ARGV[5]) then
  both = 1
end
return { 'ok', both }
`;
