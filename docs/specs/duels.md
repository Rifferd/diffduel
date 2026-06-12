# Спека: дуэли 1×1 (этап 3, MVP)

> Источник: ТЗ §4 (поток дуэли), §5–§6, §8. Контракт обязателен для apps/api, apps/realtime, apps/web.

## Роли сервисов

- **Realtime (NestJS, :8100, namespace `/duel`)** — владеет горячим состоянием: очередь, матчмейкинг, таймеры раундов, мгновенная проверка ответов против эталона из Redis, реконнект. PostgreSQL не трогает вообще.
- **Core API** — владеет долговременным состоянием: создание дуэли (выбор задач), финальная транзакция (Эло, запись результатов). Redis-состоянием дуэли не управляет.

## Формат дуэли (MVP)

5 задач × 30 секунд, обе стороны решают одновременно один и тот же индекс. Счёт = число верных; тай-брейк — меньшее суммарное время по верным ответам; полное равенство — ничья.

## Internal REST (Core API, заголовок X-Internal-Token)

```
POST /internal/duels
  { "topic": "sql", "player_a": uuid, "player_b": uuid }
  → 201 {
      "duel_id": uuid, "topic": "sql",
      "tasks": [ { "id", "type", "difficulty", "body", "answer", "time_limit_s": 30 } ×5 ],
      "ratings": { "<player_a>": 1200, "<player_b>": 1187 }
    }
  -- создаёт duels(status='running', started_at=now); 5 случайных published-задач темы;
  -- answer (эталон) отдаётся ТОЛЬКО здесь, внутреннему сервису.

POST /internal/duels/{id}/finish
  { "finished_at": iso8601,
    "results": { "<player_id>": { "answers": [ { "task_id", "selected": int|null,
                  "time_ms": int|null, "correct": bool } ×5 ] } ×2 },
    "reason": "completed" | "opponent_left" | "aborted" }
  → 200 { "winner_id": uuid|null, "deltas": { "<player_id>": +24, ... },
          "elo": { "<player_id>": 1224, ... } }
  -- ИДЕМПОТЕНТЕН: повторный вызов по finished-дуэли возвращает сохранённый результат.
  -- reason=aborted (оба отвалились до первого ответа): status='aborted', Эло не меняется.
  -- Одна транзакция: SELECT ... FOR UPDATE обеих строк ratings в детерминированном
  -- порядке (user_id ASC) → Эло → UPDATE duels, INSERT answers (duel_id), UPDATE ratings.
```

## Эло

K=32, базовый рейтинг 1200 (per-topic, таблица ratings). `expected_a = 1/(1+10^((elo_b-elo_a)/400))`; score: победа 1, ничья 0.5, поражение 0. `delta = round(K*(score-expected))`. games/wins/streak обновляются той же транзакцией (streak: победа +1, иначе 0).

## Kafka (Redpanda)

- Realtime продюсирует `answers.submitted` (key=user_id) на каждый ответ в дуэли: конверт `{v:1, type:"answers.submitted", occurred_at, payload:{duel_id, user_id, task_id, selected, correct, time_ms, idx}}`.
- Core API продюсирует `duels.finished` (key=duel_id) из finish-транзакции (после commit): payload {duel_id, topic, players, winner_id, deltas, scores}.
- Недоступность брокера НЕ ломает дуэль: produce best-effort с логом ошибки (консьюмеры — этап 4).

## Redis (горячее состояние, владеет Realtime)

```
mm:{topic}            ZSET  member=user_id, score=elo        # очередь матчмейкинга
mm:meta:{topic}       HASH  user_id → {joined_at, socket}     # для расширения окна
duel:{id}             HASH  поля: topic, players, tasks(json c эталонами), idx,
                            deadline_ts, progress(json: ответы обоих), status   TTL 2ч
user:active-duel:{uid} STRING duel_id                          TTL 2ч  # реконнект
```

Матчмейкинг: цикл раз в 1с; окно ±150 Эло, расширяется на +150 каждые 5с ожидания (макс ±600). Спаривание строго атомарно — Lua-скрипт проверяет наличие и удаляет ОБОИХ кандидатов одним вызовом (защита от гонки двух инстансов/тиков; ТЗ §11 п.10).

## WebSocket-протокол (namespace /duel, auth: handshake `auth.token` = access JWT, верификация HS256 тем же JWT_SECRET)

```
client → server:
  queue.join   {topic}            # ставит в очередь (один активный queue/duel на юзера)
  queue.leave  {}
  duel.answer  {idx, selected}    # время меряет СЕРВЕР от отправки duel.task
server → client:
  queue.searching        {widening: int}            # раз в 5с при расширении окна
  duel.matched           {duelId, topic, opponent:{username, elo}, tasksCount}
  duel.countdown         {n: 3|2|1}
  duel.task              {idx, body, deadline_ts}   # БЕЗ эталона; body как в соло
  duel.opponent_answered {idx, timeMs, correct}     # без содержимого ответа
  duel.verdict           {idx, correct, correctOption, timeMs}  # только автору ответа
  duel.finished          {winnerId|null, deltas, elo, score:{mine,opp}, reason}
  system.reconnect_state {duelId, idx, deadline_ts, progress, opponent, score}
  system.error           {code, message}
```

Правила сервера: ответ принимается один на задачу и только до deadline; после deadline_ts+грейс 1с — автопереход к следующей задаче (selected=null). Обрыв соединения: дуэль живёт; реконнект (новый сокет с валидным JWT) → `system.reconnect_state`. Если игрок не вернулся до конца дуэли — его оставшиеся ответы null, финиш по обычной схеме (reason=completed); если ни один ответ не дан обоими и оба отвалились — aborted.

## Безопасность

- Эталоны существуют только в Redis duel:{id} и internal-ответах; в WS-событиях клиенту — никогда (duel.verdict отдаёт correctOption только ПОСЛЕ ответа/дедлайна этого игрока).
- Rate limit на duel.answer не нужен (1 ответ/задачу принудительно), на queue.join — 10/мин/user в realtime.
- CORS Socket.IO: тот же белый список origin'ов (env CORS_ORIGINS).
- Internal-вызовы realtime→api: X-Internal-Token, таймаут 5с, ретрай ×2 на сетевые ошибки (finish идемпотентен).

## Env realtime

PORT=8100, REDIS_URL, JWT_SECRET, INTERNAL_API_TOKEN, CORE_API_URL=http://localhost:8000, KAFKA_BROKERS, CORS_ORIGINS, APP_ENV.
