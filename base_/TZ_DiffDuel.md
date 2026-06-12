# ТЗ: DiffDuel — арена дуэлей для разработчиков

> Домен: **diffduel.com**. Бренд: DiffDuel by **Rifferd** (рифма Riff/Diff — элемент айдентики). Ники rifferd/diffduel резервируются в GitHub, Telegram и X одновременно с доменом.

> Пет-проект уровня «в два раза выше вакансии Middle Fullstack».
> Цели по приоритету: **1) самопиар продукта и автора → 2) микро-монетизация на большой аудитории → 3) полигон для всех технологий вакансии и подготовки к собеседованию.**

---

## 1. Концепция

**Что это.** Платформа соревновательных дуэлей для разработчиков. Два игрока получают одинаковый набор задач (SQL-запрос, баг в JS-коде, вопрос по конкурентности, мини system design) и решают на скорость и точность в реальном времени. Есть соло-режим (тренировки), рейтинг Эло, ежедневные челленджи, турниры и публичные лидерборды.

**Почему именно дуэли, а не «ещё один туду-лист»:**

1. **Виральность зашита в механику.** Дуэль требует второго человека → каждый игрок сам приводит следующего («скинь ссылку коллеге»). Результат дуэли — это статус («я обошёл тимлида по SQL»), а статусом делятся добровольно.
2. **Самопиар автора.** Проект сам по себе — портфолио: он публичный, нагруженный real-time-логикой, с открытым техблогом «Rifferd строит DiffDuel AI-only». Каждая share-картинка содержит водяной знак diffduel.com. Публичные профили и лидерборды = бесплатный SEO-трафик. Бренд основателя зашит в продукт: рифма **Riff**erd / **Diff**Duel в копирайтинге, подпись «by Rifferd» в футере и changelog, публичный профиль основателя с бейджем Founder, еженедельный ивент «Вызови основателя» (пятничные дуэли против Rifferd, зал славы победителей) — регулярный инфоповод.
3. **Монетизация мелкими суммами.** Геймеры и разработчики платят за статус и прогресс: подписка Pro, разовые AI-разборы, входные билеты в турниры, косметика профиля. Чек маленький (99–399 ₽), конверсия берётся объёмом.
4. **Технологическая честность.** Real-time дуэли *невозможно* сделать без WebSocket, матчмейкинг — без Redis, аналитику ответов — без брокера, share-картинки — без фоновых задач и S3. Ни одна технология не притянута за уши — на собеседовании на вопрос «зачем тут Kafka?» будет честный продуктовый ответ.

**Аудитория.** Junior/Middle разработчики, готовящиеся к собеседованиям (огромный, вечный, постоянно обновляющийся рынок), студенты, команды (тимбилдинг-турниры).

---

## 2. Карта соответствия вакансии (что и где закрывается)

| Требование вакансии | Где в DiffDuel | Почему именно так |
|---|---|---|
| REST API, асинхронные сценарии | Core API на FastAPI (async), все I/O-операции неблокирующие | Дуэль = тысячи коротких одновременных запросов; sync-воркеры захлебнутся на ожидании БД |
| Транзакции, оптимизация запросов | Начисление рейтинга, покупки, лидерборды по сложным агрегатам | Деньги и рейтинг — классические места, где без транзакций и `SELECT ... FOR UPDATE` будут гонки |
| Redis | Матчмейкинг-очередь, лидерборды (sorted sets), кэш, rate limiting, pub/sub | Лидерборд из 100k игроков в Postgres = тяжёлый `ORDER BY` на каждый запрос; ZSET даёт O(log N) |
| Kafka/RabbitMQ | Топик `answers.submitted` → консьюмеры аналитики, антифрода, генерации картинок | Ответ игрока нужен 4 потребителям; синхронно дёргать всех — растёт латентность дуэли |
| Фоновые задачи | Генерация share-картинок, пересчёт рейтингов, дайджест-письма, очистка | Картинка рендерится 1–2 сек — нельзя держать HTTP-запрос |
| S3/MinIO, presigned URL | Аватары (presigned upload), share-картинки (presigned download) | Файлы не должны идти через API-сервер — это убивает его пропускную способность |
| ORM + SQL (JOIN, агрегации, индексы, EXPLAIN) | SQLAlchemy 2.0; страница статистики профиля = витрина оконных функций и агрегатов | Статистика «точность по темам за 90 дней» — естественный повод для EXPLAIN и индексов |
| PostgreSQL: миграции, транзакции | Alembic, ~15 таблиц, партиционирование `answers` по месяцам | Таблица ответов растёт на миллионы строк — реальный повод для партиций |
| SPA, админка, CRUD, аккуратный UI | SPA на Vue 3 + отдельная админка на React | Две библиотеки = двойное покрытие требования «Vue3/React» |
| Docker/Compose | `docker compose up` поднимает 12 сервисов локально | Иначе проект просто не запустить |
| AI-only development | Весь проект ведётся через Claude Code, артефакты в `/docs` (ADR, спеки, промпты) | Это требование вакансии — делаем его публичной фишкой проекта |
| Observability (желательно) | OpenTelemetry → Grafana/Tempo/Loki/Prometheus, Sentry | Дуэли лагают? Без трассировки не найти, где: API, Redis или WS |
| JWT, OAuth2/OIDC (желательно) | JWT access/refresh с ротацией + вход через GitHub/Google | Аудитория — разработчики, вход через GitHub обязателен продуктово |
| API-контракты (желательно) | OpenAPI → автогенерация TS-клиента; AsyncAPI для WS и Kafka | Контракт — единственный источник правды между 3 фронтендами и 2 бэкендами |
| CI/CD (желательно) | GitHub Actions: lint → test → build → push → deploy | Релизы каждый день, руками деплоить 12 контейнеров нереально |

**Сверх вакансии (×2):** второй бэкенд-сервис на TypeScript/NestJS (real-time), WebSocket-протокол, Эло-рейтинг и матчмейкинг, платежи и вебхуки, партиционирование, feature flags, Telegram-бот, PWA + мобильная оболочка, нагрузочное тестирование (k6), AsyncAPI, Traefik + TLS, секреты, бэкапы.

---

## 3. Стек и обоснование каждого выбора

> Формат: **Выбор → Почему он → Что сказать на собеседовании.**

### 3.1 Core API — Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + Alembic
- **Почему:** FastAPI даёт OpenAPI из коробки, нативный async, Pydantic-валидацию. SQLAlchemy 2.0 — самая «взрослая» ORM в Python: явная сессия, unit of work, контроль транзакций.
- **Собеседование:** «Я выбрал async-стек, потому что профиль нагрузки — много коротких I/O-bound запросов (проверка ответа = чтение из Redis + запись в PG + событие в Kafka). CPU-bound задачи (генерация картинок) вынесены в отдельный воркер, чтобы не блокировать event loop».

### 3.2 Realtime-сервис — TypeScript + NestJS + Socket.IO + Redis adapter
- **Почему отдельный сервис и другой язык:** WebSocket-соединения — это долгоживущее состояние, его жизненный цикл отличается от stateless REST. Node идеален для тысяч одновременных лёгких соединений. Бонус: в резюме появляются и Python, и TypeScript на бэкенде (вакансия принимает оба).
- **Почему Redis adapter:** при горизонтальном масштабировании (2+ инстанса realtime) события дуэли должны доходить до игроков на разных инстансах → pub/sub через Redis.
- **Собеседование:** «Разделил по характеру нагрузки: REST stateless и масштабируется тривиально, WS stateful — для него нужен sticky-session на балансировщике и шина между инстансами».

### 3.3 PostgreSQL 16
- **Почему:** транзакционная целостность (рейтинг, деньги), JSONB для гибкого содержимого задач, оконные функции для статистики, партиционирование для `answers`.
- **Собеседование:** уметь объяснить уровни изоляции (где хватает Read Committed, где нужен `FOR UPDATE` — начисление рейтинга двум игрокам одной транзакцией), отличие B-tree от GIN (GIN — на JSONB-теги задач), почему `EXPLAIN (ANALYZE, BUFFERS)`.

### 3.4 Redis 7
Карта использования (каждый пункт — отдельная тема на собеседовании):
| Применение | Структура | Зачем |
|---|---|---|
| Матчмейкинг | ZSET `mm:{topic}` score=рейтинг | Поиск соперника ±150 Эло за O(log N) через `ZRANGEBYSCORE` |
| Лидерборды | ZSET `lb:global`, `lb:weekly:{week}` | Топ-100 и «моё место» без запросов в PG |
| Кэш задач | STRING + TTL, версия в ключе | Задачи читаются в 1000 раз чаще, чем меняются |
| Rate limiting | Lua-скрипт sliding window | Анти-абьюз API и защита от брутфорса ответов |
| Состояние дуэли | HASH `duel:{id}` + TTL | Горячее состояние раунда; PG — только финальный результат |
| Pub/Sub | каналы Socket.IO adapter | Шина между инстансами realtime |
| Идемпотентность | `SETNX payment:{id}` | Вебхук платёжки может прийти дважды |

### 3.5 Kafka (в dev — Redpanda, тот же протокол, легче в Compose)
- **Топики:** `answers.submitted`, `duels.finished`, `payments.events`, `users.registered`.
- **Консьюмеры:** аналитика (агрегаты по задачам), антифрод (аномально быстрые ответы), image-generator (share-картинки), notifier (письма/телега).
- **Почему Kafka, а не RabbitMQ:** нужен replay (пересчитать аналитику с нуля новым консьюмером по сохранённому логу) и несколько независимых групп потребителей одного события. RabbitMQ — про маршрутизацию команд, Kafka — про лог событий. **На собеседовании это любимый вопрос — уметь сравнить:** очередь (сообщение исчезает после ACK) vs лог (сообщение остаётся, у каждой consumer group свой offset); гарантии at-least-once → поэтому консьюмеры обязаны быть идемпотентными.

### 3.6 Фоновые задачи — Taskiq (или Celery) поверх того же брокера
- Генерация картинок (Pillow/Playwright-рендер HTML-шаблона), пересчёт недельных лидербордов (cron), рассылки, очистка протухших матчей.
- **Собеседование:** retry с экспоненциальным бэкоффом, dead letter, идемпотентность задач, почему долгие задачи нельзя делать в HTTP-обработчике.

### 3.7 MinIO (S3 API)
- **Bucket'ы:** `avatars` (private, upload через presigned PUT), `share-cards` (public-read через CDN-префикс), `exports`.
- **Flow presigned upload:** клиент просит API → API валидирует тип/размер, выдаёт presigned PUT URL (TTL 5 мин) → клиент грузит напрямую в MinIO → клиент подтверждает → фоновая задача валидирует и ресайзит.
- **Собеседование:** «Зачем presigned?» — файл не проходит через API-сервер (экономия CPU/памяти/трафика), у URL ограниченный TTL и права на один ключ.

### 3.8 Frontend
- **Основная SPA — Vue 3 (Composition API) + Vite + Pinia + TanStack Query + TypeScript.** Vue выбран основным, потому что в РФ/СНГ-вакансиях встречается чаще; Composition API концептуально близок к React-хукам — легко объяснять перенос знаний.
- **Админка — React 18 + Vite + TanStack Table/Query.** Отдельное приложение: модерация задач, банхаммер, дашборд метрик, фичефлаги. CRUD-формы с оптимистичными обновлениями. Так в портфолио оказываются **и Vue, и React** в осмысленных ролях.
- **Контракт:** TS-типы клиента генерируются из OpenAPI (`openapi-typescript`) — руками типы не пишутся никогда.

### 3.9 Мобильная версия
- **Этап 1 — PWA:** манифест, service worker (офлайн-тренировки по закэшированным задачам), push-уведомления «тебя вызвали на дуэль». Дёшево, одна кодовая база.
- **Этап 2 — Capacitor-оболочка** той же SPA в сторы (опционально). Нативный rewrite на React Native — только если продукт взлетит.
- **Собеседование:** уметь объяснить trade-off PWA vs RN vs Flutter.

### 3.10 Auth — JWT + OAuth2/OIDC
- Access-токен 15 мин (в памяти SPA), refresh 30 дней (httpOnly cookie, ротация при каждом обновлении, reuse detection → отзыв всей семьи токенов).
- OAuth2 Authorization Code + PKCE через GitHub и Google (OIDC: валидация `id_token`, `nonce`).
- **Собеседование:** почему access нельзя в localStorage (XSS), зачем ротация refresh (кража токена обнаруживается по повторному использованию), что такое PKCE и зачем он SPA.

### 3.11 Платежи
- РФ/СНГ: ЮKassa (или CloudPayments) + **Telegram Stars** через бота; зарубеж — Stripe (одним адаптером за интерфейсом `PaymentProvider`).
- Вебхуки: проверка подписи, идемпотентность по `event_id`, начисление в транзакции, событие в Kafka.

### 3.12 Observability
- **OpenTelemetry SDK** в API, realtime и воркерах → traces в Tempo, метрики в Prometheus, логи (structured JSON) в Loki, всё в Grafana. Ошибки — Sentry.
- Ключевые метрики продукта: `duel_match_time_seconds`, `answer_check_latency`, `ws_connections`, `payment_success_rate`.
- **Собеседование:** три сигнала (logs/metrics/traces), что такое trace context propagation (заголовок `traceparent` сквозь API → Kafka → воркер), RED-метрики.

### 3.13 CI/CD — GitHub Actions
- PR: lint (ruff, eslint, mypy, tsc) → unit-тесты (pytest, vitest) → интеграционные (testcontainers: PG+Redis+Kafka) → build.
- main: build образов → push в GHCR → deploy на VPS (docker compose pull && up -d через SSH) → smoke-тест → откат при фейле.
- Traefik как reverse proxy: TLS (Let's Encrypt), маршрутизация, sticky sessions для WS.

### 3.14 AI-only development (требование вакансии → фишка проекта)
Весь проект разрабатывается через Claude Code, и это **публично документируется** — двойной пиар: продукта и автора как специалиста по AI-разработке.
- `/docs/adr/` — Architecture Decision Records (каждое решение: контекст → варианты → выбор → последствия).
- `/docs/specs/` — спецификации фич, которые подаются AI на вход (само это ТЗ — первый артефакт).
- `/docs/ai-log/` — еженедельный журнал: что делегировано AI, что пришлось править, как валидировался результат.
- **Валидация AI-кода:** контрактные тесты по OpenAPI, обязательный прогон линтеров и тестов до коммита, ревью диффа человеком, нагрузочные сценарии k6 для критичных путей.
- **Собеседование:** «Покажите, как вы работаете с AI» — открываешь репозиторий и показываешь спеку → промпт → дифф → тесты → ADR. Это сильнее любых слов.

---

## 4. Архитектура

```
                         ┌──────────────────────── Traefik (TLS, sticky WS) ───────────────────────┐
                         │                                                                          │
   Vue 3 SPA ────REST────►  Core API (FastAPI, async)  ◄──REST──── React Admin                     │
   (web + PWA)           │      │        │       │                                                 │
        │                │      │        │       └── presigned URL ──► MinIO (S3) ◄── browser PUT  │
        │                │   PostgreSQL  Redis ◄────────────────────────┐                          │
        └────WebSocket───►  Realtime (NestJS + Socket.IO) ── pub/sub ───┘                          │
                         │      │                                                                  │
                         │      └─────────► Kafka (Redpanda) ◄────── produce ── Core API           │
                         │                     │                                                   │
                         │     ┌───────────────┼───────────────┬───────────────┐                   │
                         │  analytics      antifraud      image-gen        notifier                │
                         │  consumer       consumer       worker(Taskiq)   (email/Telegram)        │
                         └──────────────────────────────────────────────────────────────────────────┘
   Observability: OTel SDK везде → Prometheus / Tempo / Loki → Grafana; ошибки → Sentry
```

**Поток дуэли (главный сценарий, знать наизусть):**
1. Игрок A жмёт «В бой» → SPA открывает WS → Realtime кладёт A в Redis ZSET `mm:sql` со score = Эло.
2. Матчмейкер (цикл в Realtime) находит B в окне ±150 Эло, расширяя окно каждые 5 сек → создаёт `duel:{id}` HASH в Redis, шлёт обоим `duel.matched`.
3. Core API отдаёт пакет задач (из Redis-кэша), Realtime синхронно стартует таймер раунда.
4. Ответ игрока → WS → Realtime валидирует против эталона в состоянии дуэли → мгновенный фидбек сопернику («A ответил за 8.2с») → событие `answers.submitted` в Kafka.
5. Финал: Realtime вызывает Core API `POST /internal/duels/{id}/finish` → **одна транзакция PG**: запись результата, пересчёт Эло обоих (`SELECT ... FOR UPDATE` на обе строки рейтинга в детерминированном порядке id — защита от дедлока), инкремент статистики → `duels.finished` в Kafka.
6. Консьюмер image-gen рендерит share-картинку → MinIO → пишет URL в дуэль → push игрокам «карточка готова».

---

## 5. Модель данных (PostgreSQL)

Основные таблицы (полный DDL живёт в миграциях Alembic):

```sql
users(id uuid pk, email citext unique, username citext unique, password_hash text null,
      avatar_key text, created_at, banned_at, role enum('user','moderator','admin'))

oauth_accounts(id, user_id fk, provider enum('github','google'), provider_user_id,
               unique(provider, provider_user_id))

refresh_tokens(id, user_id fk, family_id uuid, token_hash, expires_at, rotated_at, revoked_at)
  -- семья токенов: reuse detection отзывает всю family_id

topics(id, slug unique, title, is_active)

tasks(id uuid pk, topic_id fk, difficulty int, type enum('quiz','code_bug','sql','design'),
      body jsonb, answer jsonb, explanation text, status enum('draft','review','published'),
      author_id fk, version int)
  -- индексы: (topic_id, difficulty, status); GIN по body->'tags'

duels(id uuid pk, topic_id, status enum('matched','running','finished','aborted'),
      player_a fk, player_b fk, winner_id fk null, started_at, finished_at,
      rating_delta_a int, rating_delta_b int, share_card_key text)

answers(id bigint pk, duel_id fk null, user_id fk, task_id fk, is_correct bool,
        time_ms int, submitted_at timestamptz)
  PARTITION BY RANGE (submitted_at)  -- помесячно; самая горячая и большая таблица

ratings(user_id pk, topic_id pk, elo int default 1200, games int, wins int, streak int)

subscriptions(id, user_id, plan enum('pro'), status, current_period_end, provider, provider_sub_id)
payments(id, user_id, amount numeric(10,2), currency, status, provider, provider_event_id unique,
         purpose enum('subscription','tournament_entry','ai_review'), created_at)

tournaments(id, title, entry_fee, prize_pool, starts_at, status)
tournament_entries(tournament_id, user_id, score, place, unique(tournament_id, user_id))

task_stats(task_id pk, shown int, solved int, avg_time_ms int, p50_time_ms int)
  -- наполняется analytics-консьюмером, не считается на лету
```

**Запросы-витрины для собеседования** (реализовать и снять EXPLAIN до/после индекса):
- Точность по темам за 90 дней: `JOIN answers→tasks→topics`, `GROUP BY`, `FILTER (WHERE is_correct)`.
- Позиция в лидерборде через `RANK() OVER (ORDER BY elo DESC)` vs Redis ZSET — сравнить и объяснить, почему прод-вариант — Redis.
- Динамика Эло по дням: `date_trunc` + оконная `LAG()` для дельты.
- N+1 демонстрация: список дуэлей с игроками без/с `selectinload`.

---

## 6. API-контракты

**REST (OpenAPI 3.1, автогенерация из FastAPI; TS-клиент генерируется в CI):**

```
POST   /auth/register | /auth/login | /auth/refresh | /auth/logout
GET    /auth/oauth/{provider}/start   GET /auth/oauth/{provider}/callback
GET    /me            PATCH /me       POST /me/avatar/presign  POST /me/avatar/confirm
GET    /topics
GET    /tasks/training?topic=&difficulty=         # соло-режим
POST   /answers                                    # ответ в соло-режиме
GET    /leaderboard?scope=global|weekly&topic=
GET    /users/{username}                           # публичный профиль (SEO)
GET    /me/stats?period=90d
POST   /duels/{id}/share-card                      # форс-генерация карточки
GET    /tournaments  POST /tournaments/{id}/enter  # платный вход
POST   /billing/checkout  POST /billing/webhook/{provider}
POST   /ai/review/{duel_id}                        # Pro: AI-разбор ошибок
--- admin (отдельный роутер, RBAC) ---
CRUD   /admin/tasks (+ /publish, /reject)  GET /admin/users (+ /ban)
GET    /admin/metrics/overview             CRUD /admin/feature-flags
```

**WebSocket-протокол (AsyncAPI, namespace `/duel`):**

```
client → server: queue.join {topic} | queue.leave | duel.answer {taskIdx, answer, clientTs}
                 duel.ready | rematch.offer
server → client: queue.searching {widening} | duel.matched {duelId, opponent, tasks}
                 duel.countdown {3..1} | duel.task {idx, deadline}
                 duel.opponent_answered {idx, timeMs, correct}   # без самого ответа!
                 duel.finished {winner, deltas, stats} | duel.share_ready {url}
                 system.reconnect_state {...}   # восстановление после обрыва
```

Реконнект: состояние дуэли в Redis с TTL → при обрыве клиент шлёт `auth + duelId`, сервер возвращает снапшот. Это любимый вопрос про WS на собеседованиях.

**Kafka (AsyncAPI):** ключ партиционирования `answers.submitted` — `user_id` (порядок событий одного игрока), `duels.finished` — `duel_id`. Schema: JSON + версия в конверте события (`v`, `type`, `occurred_at`, `payload`).

---

## 7. Функциональные требования по релизам

### MVP (недели 1–4) — без него ничего не имеет смысла
- Регистрация/логин (email + GitHub OAuth), профиль, аватар через presigned upload.
- Соло-тренировки: 3 темы (SQL, JS, Python), 150 задач, мгновенная проверка, объяснения.
- Дуэли 1×1: матчмейкинг, 5 задач × 30 сек, live-статус соперника, Эло.
- Лидерборд глобальный + недельный. Публичные профили.
- Share-картинка результата (фон. задача → MinIO) с водяным знаком diffduel.com.
- Админка: CRUD задач с пайплайном draft → review → published, бан пользователей.
- Вся инфраструктура: Compose, CI, observability-минимум (Sentry + structured logs).

### Релиз 2 «Деньги» (недели 5–6)
- Подписка Pro: AI-разбор ошибок дуэли (вызов LLM в фоновой задаче, результат в профиле), расширенная статистика, кастомные темы карточек.
- Платёжный адаптер: ЮKassa + Telegram Stars; вебхуки, идемпотентность.
- Ежедневный челлендж (одна задача всем, общий лидерборд дня) — retention-петля.

### Релиз 3 «Рост» (недели 7–8)
- Турниры по расписанию с платным входом и призовым фондом.
- Telegram-бот: вызов на дуэль ссылкой в чат, уведомления.
- PWA: офлайн-тренировки, push «тебя вызвали».
- Embeddable-виджет «мой рейтинг» для README на GitHub (ещё одна виральная петля).

---

## 8. Нефункциональные требования
- p95 латентность проверки ответа в дуэли ≤ 150 мс; время матчмейкинга p50 ≤ 20 сек (при пустой очереди — бот-соперник на основе записанных «призраков» реальных игроков).
- Realtime держит 5k одновременных WS на одном инстансе (проверяется k6 + ws-сценарий).
- Восстановление дуэли после обрыва сети ≤ 3 сек.
- RPO бэкапов PG: 24 ч (pg_dump в MinIO ночной таской + проверка восстановления раз в месяц).
- Безопасность: rate limiting на auth и ответы, валидация всех входов (Pydantic/Zod), CSP, секреты только в env/secret-хранилище, ответы задач никогда не уезжают на клиент до конца раунда.

---

## 9. Монетизация (мелкий чек × масса)

| Продукт | Цена | Механика |
|---|---|---|
| Pro-подписка | 299 ₽/мес | AI-разбор ошибок, глубокая статистика, темы карточек, бейдж |
| Разовый AI-разбор | 99 ₽ | Пейволл сразу после проигранной дуэли — момент максимальной мотивации |
| Вход в турнир | 49–199 ₽ | 60% — призовой фонд, 40% — платформе |
| Telegram Stars | эквивалент | Те же продукты внутри бота без эквайринга |
| B2B-турниры | 9 900 ₽ | Приватный турнир для команды/кафедры, свой набор задач |

Виральные петли: share-картинка → вызов по ссылке → виджет в README → публичные профили в поиске → пятничный ивент «Вызови основателя» (дуэли против Rifferd, зал славы победителей) → техблог «Rifferd строит DiffDuel AI-only» (Хабр/Telegram) → приток и пользователей, и внимания работодателей.

---

## 10. Roadmap по неделям (≈ 2 месяца по вечерам)

| Нед. | Бэкенд | Фронтенд | Инфра/прочее |
|---|---|---|---|
| 1 | Скелет FastAPI, модели, Alembic, auth JWT | Скелет Vue, дизайн-токены, страницы auth | Compose: PG, Redis, MinIO; CI lint+test |
| 2 | Задачи, соло-режим, presigned avatars | Тренировка, профиль, загрузка аватара | OAuth GitHub; Sentry |
| 3 | Realtime NestJS: матчмейкинг, протокол дуэли | Экран дуэли (главный!), реконнект | Redpanda в Compose; topic answers |
| 4 | finish-транзакция, Эло, лидерборды (Redis) | Лидерборд, публичный профиль | image-gen воркер, share-карточки; деплой на VPS |
| 5 | Платёжный адаптер, вебхуки, подписки | Пейволл, экран Pro, биллинг | Идемпотентность, тесты вебхуков |
| 6 | AI-разбор (LLM в воркере), дневной челлендж | Экран разбора, челлендж | OTel-трейсы end-to-end, Grafana-дашборд |
| 7 | Турниры | Турниры; React-админка (CRUD, метрики) | k6-нагрузка дуэлей, тюнинг по EXPLAIN |
| 8 | Telegram-бот, виджет README | PWA: SW, push, манифест | Партиционирование answers; пост на Хабр |

Правило: **каждая неделя заканчивается задеплоенным инкрементом и одним ADR.**

---

## 11. Подготовка к собеседованию: вопрос → ответ из проекта

1. **«Расскажите про асинхронность в Python»** → event loop в FastAPI; почему генерация картинки в воркере, а не в эндпоинте; чем `asyncio.gather` помог в `/me/stats` (параллельные независимые запросы).
2. **«Транзакции и уровни изоляции»** → начисление Эло двум игрокам: `FOR UPDATE` в детерминированном порядке id против дедлоков; где хватило Read Committed; идемпотентное начисление платежа.
3. **«Как оптимизировали запрос?»** → история: статистика профиля 1.2 c → 40 мс: EXPLAIN ANALYZE, составной индекс `(user_id, submitted_at)`, предагрегация в `task_stats` консьюмером.
4. **«Kafka vs RabbitMQ»** → лог vs очередь; consumer groups и replay аналитики; ключи партиционирования; идемпотентность при at-least-once.
5. **«Зачем Redis, если есть Postgres?»** → таблица из §3.4; рассказ про лидерборд: ZSET O(log N) против RANK() по всей таблице.
6. **«Как устроен ваш auth?»** → ротация refresh + reuse detection; PKCE; почему access в памяти, а не в localStorage.
7. **«Vue или React?»** → «Использую оба в одном проекте по ролям: Vue — продуктовая SPA, React — админка; Composition API и хуки решают одну задачу — композицию логики».
8. **«Как работаете с AI-инструментами?»** → показать репозиторий: спека → промпт → дифф → тесты → ADR; рассказать, где AI ошибался и как это ловили (контрактные тесты, k6).
9. **«Что мониторите?»** → RED-метрики, трейс «ответ игрока» сквозь API→Kafka→воркер, алерт на p95 латентность дуэли.
10. **«Самое сложное в проекте?»** → честный ответ: восстановление состояния дуэли при реконнекте и гонки в матчмейкинге (атомарный `ZPOPMIN`/Lua вместо read-then-write).

---

## 12. Структура репозитория (монорепо)

```
diffduel/
├── apps/
│   ├── api/          # FastAPI: src/{auth,users,tasks,duels,billing,admin}/, tests/
│   ├── realtime/     # NestJS: gateway, matchmaking, duel-engine
│   ├── workers/      # Taskiq: image_gen, ai_review, digests + kafka consumers
│   ├── web/          # Vue 3 SPA (+PWA)
│   ├── admin/        # React админка
│   └── bot/          # Telegram-бот (aiogram)
├── packages/
│   ├── contracts/    # openapi.json, asyncapi.yaml, сгенерированные клиенты
│   └── ui-tokens/    # дизайн-токены (см. §13) — один источник для web/admin/карточек
├── infra/
│   ├── compose/      # docker-compose.yml, compose.observability.yml
│   ├── grafana/      # дашборды как код
│   └── deploy/       # Traefik, скрипты деплоя
├── docs/
│   ├── adr/  specs/  ai-log/  interview/   # артефакты AI-only разработки
└── .github/workflows/
```

---

## 13. Дизайн-система (общая для web и mobile)

**Метафора:** дуэль разработчиков = **git diff**. Зелёный — «принято/победа» (+), красный — «ошибка/поражение» (−). Интерфейс светлый, технический, как хороший code-review-инструмент; тёмные панели кода — акцентные «арены».

**Токены (`packages/ui-tokens`):**

```css
:root {
  /* color */
  --bg: #EEF1F5;            /* холодный светлый фон, не кремовый */
  --surface: #FFFFFF;
  --ink: #10141A;           /* текст */
  --ink-soft: #5A6472;
  --line: #D8DEE6;
  --plus: #1F9D55;          /* победа / верно / игрок-вы */
  --plus-bg: #E3F5EB;
  --minus: #E5484D;         /* поражение / ошибка / соперник */
  --minus-bg: #FDE9EA;
  --timer: #F5A623;         /* только таймер и срочность */
  --arena: #161B22;         /* тёмные панели кода/дуэли */
  --arena-ink: #E6EDF3;
  /* type */
  --font-display: "Archivo", sans-serif;   /* 800, expanded — спортивная афиша */
  --font-body: "Inter", sans-serif;
  --font-mono: "JetBrains Mono", monospace; /* код, цифры, рейтинг, таймеры */
  /* layout */
  --radius: 10px; --radius-lg: 16px;
  --space: 4px;  /* шкала ×4 */
  --shadow: 0 1px 2px rgb(16 20 26 / .06), 0 8px 24px rgb(16 20 26 / .07);
}
```

**Правила:**
- Все числа (Эло, таймеры, счёт, время ответа) — только моноширинным `JetBrains Mono`: цифры не «прыгают» при тике таймера.
- Зелёный/красный закреплены семантически (вы/соперник, верно/ошибка) и не используются декоративно.
- Сигнатурный элемент — **диагональный VS-сплит**: экран дуэли и share-карточка разделены наклонной линией 78° между зелёной и красной половинами.
- Статусы матчей оформляются как diff-строки: `+24 Elo`, `−18 Elo`.
- Доступность: контраст AA, фокус-кольца, `prefers-reduced-motion` отключает анимации таймера.

Макеты: `design_web.html` (десктоп: лендинг-арена + экран дуэли + лидерборд + блок «Вызови основателя») и `design_mobile.html` (4 ключевых экрана в рамках телефона). Оба используют эти токены — это и есть «дизайн-код».
