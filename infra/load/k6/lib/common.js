// Общие хелперы для k6-сценариев DiffDuel.
// Параметризация окружения через __ENV (см. infra/load/k6/README.md).

export const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const WS_URL = (__ENV.WS_URL || 'ws://localhost:8100').replace(/\/+$/, '');

// Тема для тренировок/дуэлей. Сид заводит sql|javascript|python.
export const TOPIC = __ENV.TOPIC || 'sql';

// JSON-заголовки для REST.
export const JSON_HEADERS = { 'Content-Type': 'application/json' };

// Уникальный суффикс для регистраций. Работает и в setup() (где __VU/__ITER не определены):
// комбинируем timestamp + растущий счётчик + random.
let _seq = 0;
export function uniqueSuffix() {
  _seq += 1;
  const rand = Math.floor(Math.random() * 1e6);
  return `${Date.now().toString(36)}${_seq}${rand.toString(36)}`;
}

import http from 'k6/http';
import { sleep } from 'k6';

// ВАЖНО ПРО RATE LIMIT. Core API лимитирует /auth/register=5/мин/IP и /auth/login=10/мин/IP,
// причём ключ — IP (а из localhost все VU = один IP). Поэтому НЕЛЬЗЯ регистрироваться на
// каждой итерации: бюджет мгновенно кончается (429). Правильный паттерн под нагрузкой —
// один раз создать пул пользователей в setup() и переиспользовать их access-токены во
// всех VU (TTL access = 15 мин, см. ACCESS_TOKEN_TTL).
//
// AUTH_POOL_SIZE (env): размер пула. По умолчанию = REGISTER_BURST (4) — помещается в одно
// окно register-лимита (5/мин), пауз нет. Если нужен пул больше — setupAuthPool делает
// паузу 61с после каждых REGISTER_BURST регистраций, чтобы не ловить 429.
const REGISTER_BURST = 4;

// setupAuthPool(n): создаёт n пользователей последовательно, соблюдая лимит register.
// Возвращает массив { token, email, username }. Вызывать ТОЛЬКО из setup().
export function setupAuthPool(n) {
  const pool = [];
  for (let i = 0; i < n; i++) {
    if (i > 0 && i % REGISTER_BURST === 0) {
      // Ждём сброса окна register-лимита (5/мин/IP).
      sleep(61);
    }
    const s = registerOrLogin();
    if (s) {
      pool.push(s);
    }
  }
  return pool;
}

// pickFromPool: детерминированно выбирает пользователя пула под текущий VU.
export function pickFromPool(pool) {
  if (!pool || pool.length === 0) {
    return null;
  }
  return pool[(__VU - 1) % pool.length];
}

// registerOrLogin: register (email_verification_enabled=false → авто-логин, access_token
// в теле) с фолбэком на login. Возвращает { token, email, username } или null.
export function registerOrLogin() {
  const suffix = uniqueSuffix();
  // ВНИМАНИЕ: домен не должен быть зарезервированным (.local/.test и т.п.) — EmailStr
  // в Core API их отклоняет (422). Используем example.com (RFC-2606, валиден для EmailStr).
  const email = `k6_${suffix}@example.com`;
  const username = `k6u${suffix}`.replace(/[^a-zA-Z0-9_]/g, '').slice(0, 24);
  const password = 'LoadTest-PW-123!';

  const regRes = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, username, password }),
    { headers: JSON_HEADERS, tags: { name: 'POST /auth/register' } },
  );

  if (regRes.status === 201) {
    const body = regRes.json();
    // Режим OFF: токен сразу в теле. Режим ON: токена нет — нужен verify (вне скоупа smoke).
    if (body && body.access_token) {
      return { token: body.access_token, email, username };
    }
  }

  // Фолбэк: пробуем логин (e.g. пользователь уже есть, или verification ON).
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password }),
    { headers: JSON_HEADERS, tags: { name: 'POST /auth/login' } },
  );
  if (loginRes.status === 200) {
    const body = loginRes.json();
    if (body && body.access_token) {
      return { token: body.access_token, email, username };
    }
  }
  return null;
}

export function authHeaders(token, name) {
  return {
    headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` },
    tags: name ? { name } : undefined,
  };
}
