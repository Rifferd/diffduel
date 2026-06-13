// duel_ws.js — WebSocket/Socket.IO нагрузка на матчмейкинг и дуэли Realtime (:8100, /duel).
//
// ЦЕЛЬ. Нагрузить матчмейкинг и измерить время до duel.matched (цель §8: матчмейкинг
// p50 ≤ 20с), плюс проверить, что Realtime держит много одновременных WS (§8: 5k на инстанс).
//
// КАК ОБРАЗУЮТСЯ ПАРЫ. Все VU делают queue.join по одной TOPIC. Матчмейкер (цикл 1с,
// окно ±150 Эло) спаривает их. Чтобы пары находились быстро, держим чётное число VU и
// все встают в очередь ~одновременно. duel_match_time меряет интервал join→matched.
//
// SOCKET.IO В K6. У k6 нет клиента Socket.IO — реализован минимальный engine.io/socket.io
// фрейминг (см. lib/socketio.js). Подключаемся напрямую по ws (transport=websocket),
// пропуская polling-handshake — сервер socket.io это разрешает и так стабильнее под нагрузкой.
//
// АУТЕНТИФИКАЦИЯ. Realtime верифицирует HS256 access-JWT тем же JWT_SECRET. Токен берём
// через REST register/login Core API и передаём в auth.token. ВАЖНО: Core API и Realtime
// должны делить один JWT_SECRET (так и есть в dev .env). Токен кладём в query
// `?EIO=4&transport=websocket&auth=...`? — нет: handshake.auth недоступен в чистом ws
// query у этого сервера, поэтому шлём Bearer в заголовке Authorization (gateway это
// поддерживает как фолбэк для не-браузерных клиентов, см. duel.gateway.ts).
//
// БЫСТРЫЙ ПРОГОН. Realtime читает DUEL_TASKS_COUNT / DUEL_TASK_SECONDS из env — для
// нагрузочного прогона запускайте realtime c DUEL_TASKS_COUNT=2 DUEL_TASK_SECONDS=3,
// чтобы дуэли завершались быстро (см. README.md).
//
// Запуск:
//   k6 run --vus 4 --iterations 4 infra/load/k6/duel_ws.js
//   WS_URL=ws://localhost:8100 BASE_URL=http://localhost:8000 k6 run infra/load/k6/duel_ws.js

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';
import { WS_URL, TOPIC, pickFromPool, setupAuthPool } from './lib/common.js';
import { decode, encodeConnect, encodeEvent, PONG } from './lib/socketio.js';

// Пул пользователей создаётся в setup(). Размер по умолчанию = числу VU, т.к. в дуэлях
// один активный queue/duel на юзера: переиспользовать одного юзера в двух VU одновременно
// нельзя (queue.join вернёт system.error). Каждому VU — свой пользователь.
const VUS = Number(__ENV.VUS || 4);
const POOL_SIZE = Number(__ENV.AUTH_POOL_SIZE || VUS);

const matchTime = new Trend('duel_match_time', true); // join → duel.matched, мс
const matched = new Counter('duel_matched_total');
const finished = new Counter('duel_finished_total');
const wsErrors = new Rate('ws_errors');

const MATCH_TIMEOUT_MS = Number(__ENV.MATCH_TIMEOUT_MS || 30000);
const DUEL_TIMEOUT_MS = Number(__ENV.DUEL_TIMEOUT_MS || 60000);

export const options = {
  // Пул пользователей создаётся в setup() с паузами под register-лимит — даём запас.
  setupTimeout: __ENV.SETUP_TIMEOUT || '300s',
  scenarios: {
    duel: {
      executor: 'shared-iterations',
      // Чётное число VU/итераций, чтобы все вставали в очередь и образовывали пары.
      vus: Number(__ENV.VUS || 4),
      iterations: Number(__ENV.ITERATIONS || 4),
      maxDuration: '2m',
    },
  },
  thresholds: {
    // Время до matched (§8: матчмейкинг p50 ≤ 20с).
    duel_match_time: ['p(50)<20000', 'p(95)<30000'],
    ws_errors: ['rate<0.05'],
  },
};

export function setup() {
  const pool = setupAuthPool(POOL_SIZE);
  if (pool.length === 0) {
    throw new Error('setup: не удалось создать ни одного пользователя (API/лимиты?)');
  }
  return { pool };
}

export default function (data) {
  const session = pickFromPool(data.pool);
  if (!session) {
    wsErrors.add(true);
    return;
  }
  const token = session.token;

  // ВАЖНО: namespace `/duel` — это понятие Socket.IO, а НЕ URL-путь. Транспорт
  // engine.io всегда живёт на /socket.io/. Namespace выбирается socket.io CONNECT-пакетом
  // `40/duel,` (см. encodeConnect()). Путь /socket.io можно переопределить через SIO_PATH.
  const path = __ENV.SIO_PATH || '/socket.io';
  const url = `${WS_URL}${path}/?EIO=4&transport=websocket`;
  const params = {
    headers: { Authorization: `Bearer ${token}` },
    tags: { name: 'WS /duel' },
  };

  let joinedAt = 0;
  let gotMatched = false;
  let gotFinished = false;
  let currentIdx = -1;

  const res = ws.connect(url, params, function (socket) {
    socket.on('open', function () {
      // engine.io пришлёт open-пакет ('0{...}') в первом message — ждём его в on('message').
    });

    socket.on('message', function (raw) {
      const frame = decode(raw);

      switch (frame.kind) {
        case 'open':
          // engine.io открыт → инициируем socket.io CONNECT в namespace /duel.
          socket.send(encodeConnect());
          break;

        case 'ping':
          // heartbeat: отвечаем pong, иначе сервер дисконнектит.
          socket.send(PONG);
          break;

        case 'connect':
          // namespace /duel подтверждён → встаём в очередь.
          joinedAt = Date.now();
          socket.send(encodeEvent('queue.join', { topic: TOPIC }));
          break;

        case 'connect_error':
          wsErrors.add(true);
          socket.close();
          break;

        case 'event':
          handleEvent(socket, frame);
          break;

        default:
          break;
      }
    });

    function handleEvent(sock, frame) {
      switch (frame.event) {
        case 'queue.searching':
          // окно расширяется — нормально, ждём дальше.
          break;

        case 'duel.matched': {
          gotMatched = true;
          matched.add(1);
          if (joinedAt > 0) {
            matchTime.add(Date.now() - joinedAt);
          }
          break;
        }

        case 'duel.countdown':
          break;

        case 'duel.task': {
          // Отвечаем сразу (selected=0). idx есть в payload.
          const idx = frame.payload && typeof frame.payload.idx === 'number'
            ? frame.payload.idx
            : currentIdx + 1;
          currentIdx = idx;
          // лёгкая «человеческая» задержка перед ответом
          sock.setTimeout(function () {
            sock.send(encodeEvent('duel.answer', { idx, selected: 0 }));
          }, 200);
          break;
        }

        case 'duel.verdict':
        case 'duel.opponent_answered':
          break;

        case 'duel.finished':
          gotFinished = true;
          finished.add(1);
          sock.close();
          break;

        case 'system.reconnect_state':
          break;

        case 'system.error':
          wsErrors.add(true);
          break;

        default:
          break;
      }
    }

    // Страховочный таймаут на матчмейкинг.
    socket.setTimeout(function () {
      if (!gotMatched) {
        wsErrors.add(true);
      }
      socket.close();
    }, MATCH_TIMEOUT_MS);

    // Жёсткий потолок на всю дуэль.
    socket.setTimeout(function () {
      socket.close();
    }, DUEL_TIMEOUT_MS);

    socket.on('error', function (e) {
      // 'websocket: close sent' при штатном закрытии — не считаем ошибкой.
      if (e && e.error && String(e.error).indexOf('close sent') === -1) {
        wsErrors.add(true);
      }
    });
  });

  check(res, { 'ws handshake 101': (r) => r && r.status === 101 });
  check(gotMatched, { 'got duel.matched': (m) => m === true });
  // duel.finished необязателен (зависит от DUEL_TASK_SECONDS и парности) — не строгий.
  if (!gotMatched && !gotFinished) {
    // уже учтено в ws_errors через таймаут
  }
  sleep(0.2);
}
