# DiffDuel — нагрузочные тесты (k6)

Сценарии k6 против **локального dev-стека**. Проверяют REST Core API (:8000) и
Realtime WebSocket (:8100, Socket.IO namespace `/duel`), а пороги привязаны к
нефункциональным требованиям ТЗ §8.

## Файлы

| Файл | Что проверяет | Ключевой порог |
|---|---|---|
| `http_smoke.js` | Счастливый путь REST: auth → `/topics` → `/tasks/training` → `/answers` → `/leaderboard` | p95 REST < 300мс, error rate < 1% |
| `answers_load.js` | Латентность **проверки ответа** (соло `POST /answers`) | p95 `answer_check_latency` < **150мс** (§8) |
| `duel_ws.js` | Матчмейкинг и игровой цикл дуэли через WS/Socket.IO | `duel_match_time` p50 < 20000мс (§8) |
| `lib/common.js` | Хелперы: env, auth-пул, заголовки | — |
| `lib/socketio.js` | Минимальный клиент Socket.IO/engine.io поверх `k6/ws` | — |

## Предусловия

1. **k6** установлен: `k6 version` (если нет — `brew install k6`).
2. **Dev-стек поднят**: `make up` (postgres, redis, redpanda, minio).
3. **Core API на :8000** запущен и засеян:
   ```bash
   curl http://localhost:8000/healthz          # {"status":"ok",...}
   # если не поднят:
   cd apps/api
   export DATABASE_URL='postgresql+asyncpg://diffduel:diffduel@localhost:5432/diffduel'
   export REDIS_URL='redis://localhost:6379/0' APP_ENV=dev KAFKA_BROKERS='localhost:19092'
   uv run alembic upgrade head
   uv run python -m src.seeds        # 3 темы (sql/javascript/python), 150 задач
   uv run uvicorn src.main:app --port 8000 &
   ```
4. Для `duel_ws.js` дополнительно **Realtime на :8100**. Чтобы дуэли завершались
   быстро под нагрузкой, запускайте Realtime с укороченным форматом
   (поддерживается из коробки, см. `apps/realtime/src/config/env.schema.ts`):
   ```bash
   cd apps/realtime
   DUEL_TASKS_COUNT=2 DUEL_TASK_SECONDS=3 pnpm start
   ```

## Параметры окружения (`__ENV`)

| Переменная | Default | Назначение |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | Core API |
| `WS_URL` | `ws://localhost:8100` | Realtime WS (без `/duel`, добавляется сценарием) |
| `TOPIC` | `sql` | Тема для тренировок/дуэлей |
| `VUS` | зависит от сценария | Число виртуальных пользователей |
| `DURATION` | зависит | Длительность (для constant-vus сценариев) |
| `AUTH_POOL_SIZE` | 4 (duel — `=VUS`) | Размер пула предсозданных пользователей |
| `ITERATIONS` | 4 (duel) | Число дуэльных итераций |
| `MATCH_TIMEOUT_MS` | 30000 | Таймаут ожидания `duel.matched` |

## Запуск

```bash
# Дымовой прогон REST (малые VU — для проверки работоспособности):
k6 run --vus 5 --duration 10s infra/load/k6/http_smoke.js

# Латентность проверки ответа:
VUS=10 DURATION=30s k6 run infra/load/k6/answers_load.js

# WS / матчмейкинг (чётное число VU/итераций — образуют пары):
WS_URL=ws://localhost:8100 k6 run --vus 4 --iterations 4 infra/load/k6/duel_ws.js

# Против другого хоста:
BASE_URL=http://api.dev:8000 WS_URL=ws://rt.dev:8100 k6 run infra/load/k6/http_smoke.js
```

> На слабом dev-железе пороги могут не проходить — это ожидаемо. Цель сценариев —
> **рабочая методология и воспроизводимость**, а не абсолютные цифры. «Боевые» числа
> снимаются на железе/конфиге, близком к прод (пул соединений, индексы, прогрев).

## Как читать результаты

- **`█ THRESHOLDS`** — пройдены ли пороги (✓/✗). Это главный вердикт.
- **`http_req_duration` p(95)** — латентность REST end-to-end. Для `answers_load` смотрите
  кастомную **`answer_check_latency`** (только `POST /answers`, без auth/тренировки).
- **`checks`** — доля успешных функциональных проверок (должна быть ~100%).
- **`http_req_failed` / `*_errors`** — доля ошибок.
- **`duel_match_time`** (duel_ws) — распределение времени `queue.join → duel.matched`;
  `duel_matched_total` / `duel_finished_total` — счётчики.

## Пороги и привязка к §8

| Метрика сценария | Порог | Требование §8 |
|---|---|---|
| `answer_check_latency` p95 | < 150мс | p95 проверки ответа в дуэли ≤ 150мс |
| `duel_match_time` p50 | < 20000мс | матчмейкинг p50 ≤ 20с |
| `http_req_duration` p95 (smoke) | < 300мс | общий REST-бюджет (мягче «боевого») |
| одновременные WS | — | 5k WS на инстанс Realtime (см. ниже) |

## Про rate limiting (важно для методологии)

Core API лимитирует `/auth/register` = **5/мин/IP** и `/auth/login` = **10/мин/IP**,
ключ — **IP** (из localhost все VU = один IP). Поэтому сценарии **не** регистрируются
на каждой итерации, а создают **пул пользователей один раз в `setup()`** и
переиспользуют их access-токены (TTL access = 15 мин). `POST /answers` лимитирован
**60/мин/пользователя** — поэтому `answers_load.js` по умолчанию держит **пул = числу VU**
(один юзер на VU) и шлёт `ANSWERS_PER_ITER` (default 2) ответов за итерацию с паузой, чтобы
темп оставался ниже 60/мин/юзер. Для прогона на ПРОПУСКНУЮ СПОСОБНОСТЬ (а не латентность)
поднимите лимит в test-профиле API или гоните с бо́льшим `AUTH_POOL_SIZE`.

## Как наращивать до 5k WS (§8)

`duel_ws.js` использует `shared-iterations`; для стресса замените на `ramping-vus`:

```js
scenarios: {
  duel: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '2m', target: 1000 },
      { duration: '3m', target: 5000 },   // цель §8: 5k WS на ОДИН инстанс realtime
      { duration: '5m', target: 5000 },   // удержание
      { duration: '1m', target: 0 },
    ],
  },
}
```

Практика для 5k одновременных WS с одной машины:

1. **fd-лимит**: `ulimit -n 1048576` перед `k6 run` (каждое WS = открытый сокет).
2. **Память/CPU агента**: ~5k VU держащих ws — это ОЗУ и GC; следите за `dropped_iterations`.
3. **Пул пользователей**: `AUTH_POOL_SIZE` ≥ числа одновременных VU (в дуэли один
   активный queue/duel на юзера — нельзя делить пользователя между VU). Пул на 5k
   создаётся с паузами под register-лимит — это долго; для больших прогонов засевайте
   пользователей напрямую в БД отдельным скриптом или поднимайте лимиты в test-окружении.
4. **Распределённый прогон**: одна k6-машина обычно упирается раньше 5k «тяжёлых» VU —
   используйте несколько агентов / k6 Cloud, при этом **цель — 5k WS на один инстанс
   Realtime** (а не на один k6-агент). Меряйте на стороне Realtime (метрики сокетов).

## Socket.IO в k6 — принятое решение

У k6 нет встроенного клиента Socket.IO, а Realtime (`@WebSocketGateway`) говорит по
**Socket.IO v4 поверх engine.io v4**. Реализован минимальный фрейминг вручную
(`lib/socketio.js`) поверх встроенного `k6/ws`:

- **URL/namespace**: транспорт engine.io живёт на `/socket.io/`
  (`ws://host:8100/socket.io/?EIO=4&transport=websocket`); namespace `/duel` — это
  понятие Socket.IO, выбирается CONNECT-пакетом `40/duel,`, а НЕ частью URL.
- **Handshake**: подключаемся **сразу по websocket** (`?EIO=4&transport=websocket`),
  пропуская polling-фазу. socket.io-сервер это разрешает, и под нагрузкой это стабильнее,
  чем эмуляция HTTP-polling-upgrade.
- **Auth**: access-JWT шлём в заголовке `Authorization: Bearer` (gateway поддерживает
  это как фолбэк для не-браузерных клиентов; `handshake.auth.token` в чистом ws-режиме
  k6 недоступен).
- **Протокол**: вручную кодируем/декодируем engine.io (`0` open, `2/3` ping/pong,
  `4` message) и socket.io (`40` CONNECT, `42` EVENT) с namespace `/duel`. Отвечаем на
  heartbeat (`2`→`3`), иначе сервер дисконнектит.

Альтернатива — `xk6-websockets` или кастомная сборка k6 с socket.io-расширением; от неё
отказались ради нулевых зависимостей (чистый `k6/ws`, запускается где угодно).
```
