// answers_load.js — фокус на p95 латентности ПРОВЕРКИ ОТВЕТА (соло POST /answers).
//
// Цель §8: p95 проверки ответа в дуэли ≤ 150мс. В дуэли проверка идёт в Realtime
// против эталона из Redis; здесь мы измеряем ближайший REST-аналог — соло-проверку
// в Core API (POST /answers), которая бьёт в Postgres+Redis(rate-limit) по тому же
// горячему пути сериализации/валидации. Методология одинакова; абсолютные цифры на
// dev-железе будут другими (нет прогрева, нет prod-индексов/пула) — важно, что прогон
// воспроизводим и порог явный.
//
// Запуск:
//   k6 run infra/load/k6/answers_load.js
//   VUS=20 DURATION=30s k6 run infra/load/k6/answers_load.js
//
// Порог: p95 кастомной метрики answer_check_latency < 150мс.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';
import { BASE_URL, TOPIC, authHeaders, pickFromPool, setupAuthPool } from './lib/common.js';

// POST /answers лимитирован 60/мин/ПОЛЬЗОВАТЕЛЯ. Чтобы не упереться в 429, держим
// пул размером с число VU (один юзер на VU) и шлём не больше ANSWERS_PER_ITER ответов
// за итерацию с паузой между итерациями. При наращивании VU пул растёт автоматически.
const VUS = Number(__ENV.VUS || 10);
const POOL_SIZE = Number(__ENV.AUTH_POOL_SIZE || VUS);
const ANSWERS_PER_ITER = Number(__ENV.ANSWERS_PER_ITER || 2);

// Изолированная метрика: только время ответа POST /answers (без auth/тренировки).
const answerCheckLatency = new Trend('answer_check_latency', true);
const answerErrors = new Rate('answer_errors');

export const options = {
  // Пул пользователей создаётся в setup() с паузами под register-лимит — даём запас.
  setupTimeout: __ENV.SETUP_TIMEOUT || '300s',
  scenarios: {
    answers: {
      executor: 'constant-vus',
      vus: VUS,
      duration: __ENV.DURATION || '30s',
    },
  },
  thresholds: {
    // Цель §8 для проверки ответа.
    answer_check_latency: ['p(95)<150'],
    answer_errors: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

// setup() один раз: создаёт пул пользователей (обход register=5/мин/IP) и делает warm-up,
// чтобы первый «холодный» запрос не портил p95. Токены переиспользуются всеми VU.
export function setup() {
  const pool = setupAuthPool(POOL_SIZE);
  if (pool.length === 0) {
    throw new Error('setup: не удалось создать ни одного пользователя (API/лимиты?)');
  }
  // warm-up: прогреваем горячий путь /answers одним запросом.
  const s = pool[0];
  const train = http.get(
    `${BASE_URL}/tasks/training?topic=${encodeURIComponent(TOPIC)}&limit=1`,
    authHeaders(s.token),
  );
  const tasks = train.status === 200 ? train.json() : null;
  if (Array.isArray(tasks) && tasks.length > 0) {
    http.post(
      `${BASE_URL}/answers`,
      JSON.stringify({ task_id: tasks[0].id, answer: { selected: 0 }, time_ms: 1000 }),
      authHeaders(s.token),
    );
  }
  return { pool };
}

export default function (data) {
  const session = pickFromPool(data.pool);
  if (!session) {
    answerErrors.add(true);
    sleep(1);
    return;
  }
  const token = session.token;

  // Берём пул задач один раз на итерацию, затем долбим /answers по разным task_id.
  const trainRes = http.get(
    `${BASE_URL}/tasks/training?topic=${encodeURIComponent(TOPIC)}&limit=10`,
    authHeaders(token, 'GET /tasks/training'),
  );
  if (trainRes.status !== 200) {
    answerErrors.add(true);
    sleep(1);
    return;
  }
  const tasks = trainRes.json();
  if (!Array.isArray(tasks) || tasks.length === 0) {
    answerErrors.add(true);
    sleep(1);
    return;
  }

  // Не больше ANSWERS_PER_ITER ответов за итерацию — держим темп под лимитом 60/мин/юзер
  // (один юзер = один VU). С sleep(1) ниже это ~ANSWERS_PER_ITER ответов/сек/юзер.
  const batch = tasks.slice(0, ANSWERS_PER_ITER);
  for (const task of batch) {
    const payload = JSON.stringify({
      task_id: task.id,
      answer: { selected: 0 },
      time_ms: 1200,
    });
    const res = http.post(`${BASE_URL}/answers`, payload, authHeaders(token, 'POST /answers'));
    // res.timings.duration — полное время запроса (TTFB + получение тела).
    answerCheckLatency.add(res.timings.duration);
    const ok = check(res, { 'answer 200': (r) => r.status === 200 });
    answerErrors.add(!ok);
  }

  // Пауза, чтобы суммарный темп на пользователя не превышал 60/мин/юзер (см. README).
  // ~ANSWERS_PER_ITER ответов / (ANSWERS_PER_ITER + 1)с ≈ ниже лимита при дефолтах.
  sleep(ANSWERS_PER_ITER + 1);
}
