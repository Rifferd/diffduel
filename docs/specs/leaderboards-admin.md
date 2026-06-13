# Спека: лидерборды, публичные профили, share-карточки, админка (этап 4)

> Источник: ТЗ §3.4 (Redis ZSET), §4 (image-gen), §5–§6, §7 (MVP), §13 (водяной знак). Контракт для apps/api, apps/workers, apps/admin, apps/web.

## A. Лидерборды (Core API + Redis ZSET)

ZSET-ключи: `lb:global` (member=user_id, score=сумма Эло по всем темам ИЛИ Эло выбранной темы — см. ниже), `lb:topic:{slug}`, `lb:weekly:{iso_year}-W{week}`. Источник истины по Эло — PostgreSQL (`ratings`); ZSET — производный кэш для O(log N) чтения.

- Обновление: после finish-транзакции (тот же путь, что `duels.finished`) Core API делает `ZADD lb:topic:{slug}` и `ZADD lb:weekly:{week}` новым Эло обоих игроков. Глобальный score = max Эло среди тем игрока (простое и осмысленное для MVP; задокументировать в ADR).
- `GET /leaderboard?scope=global|weekly&topic=<slug?>&limit=50` (публичный, без auth): топ-N через `ZREVRANGE ... WITHSCORES`, обогащение username/avatar батч-запросом в PG (один `WHERE id = ANY(:ids)`, без N+1). Ответ: `[{rank, user_id, username, avatar_url, elo}]`.
- `GET /leaderboard/me?scope=&topic=` (auth): моя позиция через `ZREVRANK` + соседи ±2. Если меня нет в ZSET — rank=null.
- **Восстановление ZSET из PG** (на случай потери Redis): идемпотентная команда `python -m src.leaderboard_rebuild` — читает ratings, наполняет все ZSET. Вызывается и при старте, если ключи пусты (ленивая регидратация в эндпоинте: если ZSET пуст — один раз перестроить из PG).

## B. Публичные профили (SEO, ТЗ §6)

`GET /users/{username}` (публичный): профиль без чувствительных данных — username, avatar_url, created_at, агрегаты: Эло по темам (из ratings), всего дуэлей/побед, винрейт, текущий streak. Запрос статистики — один JOIN ratings+агрегаты по answers/duels с разумными индексами (сними EXPLAIN, опиши в ADR; это витрина для собеседования). Забаненные (banned_at) → 404. Несуществующий → 404.

## C. Share-карточки (worker image-gen, ТЗ §4 шаг 6, §13)

`apps/workers` (Python, тот же стиль что api): консьюмер топика `duels.finished` (aiokafka, idempotent по duel_id) → рендер PNG-карточки результата → upload в MinIO bucket `share-cards` (public-read) → PATCH дуэли `share_card_key` через internal-эндпоинт Core API (`POST /internal/duels/{id}/share-card` {key}) → (push игрокам — вне MVP, просто записать ключ).
- Рендер: Pillow (без headless-браузера — легче на 4GB VPS). Карточка 1200×630 (OG-формат): диагональный VS-сплит (зелёная/красная половины по §13, для ничьей — серые тона из токенов), ник победителя/счёт/дельты Эло моноширинным, **водяной знак `diffduel.com`** обязателен. Шрифты — положить в apps/workers/assets (JetBrains Mono + Archivo, или дефолтные если лицензия неясна — но мономоноширинный для цифр обязателен).
- Консьюмер идемпотентен: если у дуэли уже есть share_card_key — пропустить. at-least-once.
- Запуск воркера отдельным процессом/контейнером. Тест: рендер карточки из фикстуры (проверить, что PNG валиден и непустой, содержит водяной знак — хотя бы что функция отрабатывает и размер кадра верный); консьюмер идемпотентен (мок internal + повторное событие).
- `GET /me/duels/recent` или включить share_card_key в существующий ответ — не требуется для MVP; достаточно записать ключ.

## D. React-админка (apps/admin)

Отдельное приложение: React 18 + Vite + TS + TanStack Query + TanStack Table + React Router. ESLint/Prettier как в web. Дизайн — packages/design-system/design/pages/admin/*.html (shell, dashboard, tasks, task-edit, users, flags) — разметку/классы дословно. Контракт-типы — из packages/contracts (общий с web).

Admin REST (Core API, роутер /admin, RBAC: только role in (moderator, admin); проверка в dependency поверх get_current_user):
- `GET /admin/tasks?status=&topic=&page=` (пагинация), `POST /admin/tasks`, `PATCH /admin/tasks/{id}`, `POST /admin/tasks/{id}/publish`, `POST /admin/tasks/{id}/reject` — пайплайн draft→review→published; валидация body/answer по типу (quiz: options≥2, correct в диапазоне).
- `GET /admin/users?q=&page=`, `POST /admin/users/{id}/ban` {reason}, `POST /admin/users/{id}/unban` — только admin (не moderator).
- `GET /admin/metrics/overview`: счётчики (users, duels за 24ч/7д, published tasks, активные подписки) — простые агрегаты.
- `GET /admin/feature-flags`, `PUT /admin/feature-flags/{key}` {enabled, payload?} — таблица feature_flags (новая, миграция 0003): key unique, enabled bool, payload jsonb, updated_at. Чтение флагов кэшируется в Redis (TTL 30с).
- Логин админки — тот же /auth/login; SPA админки хранит access в памяти, гейтит по роли (не-админа на /login с сообщением).

Тесты API: RBAC (user→403, moderator→tasks ok но users/ban→403, admin→всё); пайплайн публикации; бан/разбан; фиче-флаг CRUD + кэш-инвалидация. Admin SPA: lint/typecheck/build + хотя бы 1-2 component-теста (логин-гейт по роли, таблица задач рендерит из мока).

## E. Деплой (infra/deploy) — готовим, НЕ применяем

ЖДЁМ доступ к новому VPS (2 vCPU/4GB) от пользователя — до этого только подготовка артефактов:
- `infra/compose/docker-compose.prod.yml`: все сервисы (api, realtime, workers, web-static через nginx или traefik, postgres, redis, redpanda, minio) с memory-limits (api 512M, realtime 512M, workers 384M, redpanda 600M, pg 768M, redis 256M, minio 256M — суммарно <4G с запасом), restart policy, healthchecks, без проброса портов наружу кроме traefik.
- `infra/deploy/traefik`: Traefik v3, TLS Let's Encrypt (diffduel.com + www), роутеры: web SPA на `/`, api на `/api`, realtime WS на `/socket` со sticky sessions, admin на отдельном поддомене или пути `/admin`. HTTP→HTTPS редирект, security-заголовки (HSTS, CSP).
- `.env.prod.example` со ВСЕМИ прод-переменными (заглушки), генерация секретов задокументирована.
- `.github/workflows/deploy.yml`: на push в main после зелёных api/web/realtime CI — build образов → push в GHCR → SSH на VPS → `docker compose pull && up -d` → smoke (healthz) → откат при фейле. Workflow пишем, но он не сработает без секретов (SSH_KEY, VPS_HOST) — это нормально, активируем после получения VPS.
- ADR по деплою и backup-стратегии (pg_dump в MinIO ночной таской — описать, реализация cron-таски опциональна для MVP).
