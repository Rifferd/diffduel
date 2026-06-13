# @diffduel/realtime

Realtime-сервис дуэлей DiffDuel: NestJS 10 + Socket.IO 4 + Redis adapter.
Владеет горячим состоянием — очередью матчмейкинга, таймерами раундов, мгновенной
проверкой ответов против эталона в Redis и реконнектом. PostgreSQL не трогает:
долговременное состояние (создание дуэли, финальная Эло-транзакция) — за Core API
через internal REST.

Контракт (WS-протокол, Redis-ключи, internal API, env) — **источник правды**:
[`docs/specs/duels.md`](../../docs/specs/duels.md). Конвенции TS —
[`docs/specs/conventions.md`](../../docs/specs/conventions.md).

## Запуск

```bash
# из корня монорепо
npm exec -y pnpm@9 -- install
npm exec -y pnpm@9 -- -C apps/realtime start:dev   # watch, :8100

# прод-сборка
npm exec -y pnpm@9 -- -C apps/realtime build
npm exec -y pnpm@9 -- -C apps/realtime start       # node dist/main.js
```

Нужны живые Redis (:6379) и Redpanda (:19092) — см. `infra/compose/docker-compose.yml`.
Health-чек: `GET /healthz` → `200 {"status":"ok","redis":"up"}` (пингует Redis).

## Переменные окружения

Валидируются Zod на старте (fail fast), имена — из спеки.

| Env | Назначение | Дефолт |
|---|---|---|
| `APP_ENV` | `dev` \| `test` \| `prod` (в prod — JSON-логи) | `dev` |
| `PORT` | HTTP/WS порт | `8100` |
| `REDIS_URL` | Redis (состояние + Socket.IO adapter pub/sub) | `redis://localhost:6379/0` |
| `JWT_SECRET` | HS256-секрет для верификации access-токена (тот же, что в Core API) | — (обязателен) |
| `INTERNAL_API_TOKEN` | `X-Internal-Token` для вызовов Core API | — (обязателен) |
| `CORE_API_URL` | базовый URL Core API | `http://localhost:8000` |
| `KAFKA_BROKERS` | брокеры Redpanda (CSV) | `localhost:19092` |
| `CORS_ORIGINS` | белый список origin'ов (CSV) | `http://localhost:5173,http://localhost:5174` |
| `DUEL_TASKS_COUNT` | число задач в дуэли (для ускорения e2e-тестов) | `5` |
| `DUEL_TASK_SECONDS` | лимит на задачу | `30` |

## WebSocket-протокол (namespace `/duel`)

Полное описание — в спеке. Кратко:

- **Handshake:** `auth.token` = access JWT (HS256). Невалидный → `system.error` + disconnect.
- **client → server:** `queue.join {topic}` · `queue.leave {}` · `duel.answer {idx, selected}`
- **server → client:** `queue.searching` · `duel.matched` · `duel.countdown` · `duel.task` ·
  `duel.verdict` (только автору, с `correctOption`) · `duel.opponent_answered` (без `selected`) ·
  `duel.finished` · `system.reconnect_state` · `system.error`

### Решения сверх спеки (задокументировано)

- **Несколько вкладок одного юзера** не вытесняют друг друга. Все сокеты юзера входят в
  комнату `user:{id}`; события адресуются комнате, поэтому все вкладки синхронны.
  Из очереди юзер удаляется только когда отключился ПОСЛЕДНИЙ его сокет.
- **Атомарность ответа.** Запись ответа в `duel:{id}.progress` (append + проверка
  «уже отвечал» + детект «оба ответили») делается одним Lua-скриптом
  (`src/duel/lua-scripts.ts`) — read-modify-write из Node гонит при двух одновременных
  ответах (в т.ч. на разных инстансах).
- **Дедлайн** проверяется и таймером, и по серверному времени при ответе
  (`now > deadline_ts + 1s grace`) — таймер может не сработать (рестарт), проверка времени
  сработает всегда. Восстановление таймеров после рестарта — вне MVP (по спеке).
- **reason=aborted** выводится автоматически: если на финише ни один из игроков не дал
  ни одного реального ответа (`selected` везде `null`), финиш идёт с `reason=aborted`.

## Тесты

`npm exec -y pnpm@9 -- -C apps/realtime test` (Vitest). Требуют живой Redis на
`localhost:6379` (используется БД `/14`) и Redpanda для e2e (best-effort).

- `lua-pairing.spec.ts` — атомарное спаривание/leave против реального Redis.
- `duel-engine.spec.ts` — один-ответ-на-задачу, дедлайн, верно/неверно, финиш+score, aborted.
- `elo-cache.spec.ts` — кэш Эло.
- `duel-reconnect.spec.ts` — `system.reconnect_state`.
- `duel-e2e.spec.ts` — два socket.io-клиента против поднятого in-process приложения
  (`internal-client` замокан, формат сокращён до 2 задач через env): join → matched →
  countdown → задачи → finished с корректным счётом.

## Docker

```bash
# из корня монорепо
docker build -f apps/realtime/Dockerfile -t diffduel-realtime .
```
Multi-stage, `node:22-alpine`, prod-зависимости и `dist` в финальном слое.
