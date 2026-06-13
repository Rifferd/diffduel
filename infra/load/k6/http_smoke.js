// http_smoke.js — базовый дымовой нагрузочный прогон REST Core API.
//
// Покрывает счастливый путь: register/login → GET /topics → GET /tasks/training
// → POST /answers → GET /leaderboard.
//
// Запуск (см. README.md):
//   k6 run --vus 5 --duration 10s infra/load/k6/http_smoke.js
//   BASE_URL=http://localhost:8000 k6 run infra/load/k6/http_smoke.js
//
// Пороги (§8/скоуп): p95 REST < 300мс, error rate < 1%.

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { BASE_URL, TOPIC, authHeaders, pickFromPool, setupAuthPool } from './lib/common.js';

const errorRate = new Rate('smoke_errors');

const POOL_SIZE = Number(__ENV.AUTH_POOL_SIZE || 4);

// setup() выполняется ОДИН раз: создаёт пул пользователей (обходит register=5/мин/IP),
// токены переиспользуются всеми VU во всех итерациях (TTL access = 15 мин).
export function setup() {
  const pool = setupAuthPool(POOL_SIZE);
  if (pool.length === 0) {
    throw new Error('setup: не удалось создать ни одного пользователя (API/лимиты?)');
  }
  return { pool };
}

export const options = {
  // Пул пользователей создаётся в setup() с паузами под register-лимит — даём запас.
  setupTimeout: __ENV.SETUP_TIMEOUT || '300s',
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || '10s',
    },
  },
  thresholds: {
    // p95 < 300мс на REST (мягче «боевых» 150мс из §8 — это дымовой прогон).
    http_req_duration: ['p(95)<300'],
    // Error rate < 1%.
    smoke_errors: ['rate<0.01'],
    // Встроенный k6: доля failed-проверок.
    checks: ['rate>0.99'],
  },
};

function track(res, ok) {
  errorRate.add(!ok);
}

export default function (data) {
  // 1. Берём заранее созданного пользователя из пула (без register/login на горячем пути).
  const session = pickFromPool(data.pool);
  const authOk = check(session, { 'authenticated': (s) => s !== null && !!s.token });
  track({ status: authOk ? 200 : 0 }, authOk);
  if (!session) {
    sleep(1);
    return;
  }
  const token = session.token;

  // 2. GET /topics — публичный список тем.
  group('topics', () => {
    const res = http.get(`${BASE_URL}/topics`, { tags: { name: 'GET /topics' } });
    const ok = check(res, {
      'topics 200': (r) => r.status === 200,
      'topics is array': (r) => Array.isArray(r.json()),
    });
    track(res, ok);
  });

  // 3. GET /tasks/training — соло-режим (auth).
  let taskId = null;
  group('training', () => {
    const res = http.get(
      `${BASE_URL}/tasks/training?topic=${encodeURIComponent(TOPIC)}&limit=5`,
      authHeaders(token, 'GET /tasks/training'),
    );
    const ok = check(res, {
      'training 200': (r) => r.status === 200,
      'training has tasks': (r) => {
        const body = r.json();
        return Array.isArray(body) && body.length > 0;
      },
    });
    track(res, ok);
    if (res.status === 200) {
      const body = res.json();
      if (Array.isArray(body) && body.length > 0) {
        taskId = body[0].id;
      }
    }
  });

  // 4. POST /answers — отправка ответа (соло). selected=0: верность не важна для smoke.
  group('answers', () => {
    if (!taskId) {
      return;
    }
    const payload = JSON.stringify({
      task_id: taskId,
      answer: { selected: 0 },
      time_ms: 1500,
    });
    const res = http.post(`${BASE_URL}/answers`, payload, authHeaders(token, 'POST /answers'));
    const ok = check(res, {
      'answers 200': (r) => r.status === 200,
      'answers has correct field': (r) => {
        const b = r.json();
        return b !== null && typeof b.correct === 'boolean';
      },
    });
    track(res, ok);
  });

  // 5. GET /leaderboard — глобальный.
  group('leaderboard', () => {
    const res = http.get(
      `${BASE_URL}/leaderboard?scope=global&limit=20`,
      { tags: { name: 'GET /leaderboard' } },
    );
    const ok = check(res, {
      'leaderboard 200': (r) => r.status === 200,
      'leaderboard is array': (r) => Array.isArray(r.json()),
    });
    track(res, ok);
  });

  sleep(1);
}
