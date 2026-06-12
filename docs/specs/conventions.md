# Инженерные конвенции DiffDuel

> Обязательны для всех приложений монорепо. Изменения — только через ADR.

## Сервисы и порты (dev)

| Сервис | Compose-имя | Порт (host) | Учётки dev |
|---|---|---|---|
| PostgreSQL 16 | `postgres` | 5432 | `diffduel` / `diffduel`, БД `diffduel` |
| Redis 7 | `redis` | 6379 | без пароля (dev) |
| Redpanda (Kafka) | `redpanda` | 19092 (host) / 9092 (внутри сети) | — |
| MinIO | `minio` | 9000 (S3), 9001 (console) | `diffduel` / `diffduel-dev-secret` |
| Core API | `api` | 8000 | — |
| Realtime | `realtime` | 8100 | — |
| Web SPA (vite dev) | — | 5173 | — |
| Admin (vite dev) | — | 5174 | — |

Compose project name: `diffduel`. Бакеты MinIO: `avatars` (private), `share-cards` (public-read), `exports` (private).

## Переменные окружения (единые имена везде)

```
APP_ENV=dev|test|prod
DATABASE_URL=postgresql+asyncpg://diffduel:diffduel@localhost:5432/diffduel
REDIS_URL=redis://localhost:6379/0
KAFKA_BROKERS=localhost:19092
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY / S3_SECRET_KEY
S3_PUBLIC_BASE_URL=http://localhost:9000   # CDN-префикс в проде
JWT_SECRET                                  # >=64 случайных байт; в проде только из секретов
ACCESS_TOKEN_TTL=900  REFRESH_TOKEN_TTL=2592000   # секунды
INTERNAL_API_TOKEN                          # auth realtime→api /internal/*
SENTRY_DSN=                                 # пусто = выключено
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

`.env` не коммитится никогда; эталон — `.env.example` в корне. Секреты прода — GitHub Secrets → env на сервере.

## Python (apps/api, apps/workers, apps/bot)

- Python 3.12, менеджер **uv**, конфиг в `pyproject.toml`.
- Линт/формат: **ruff** (line-length 100, `select = ["E","F","I","UP","B","S","ASYNC"]`), типы: **mypy --strict** (допускаются точечные исключения с комментарием-причиной).
- Тесты: pytest + pytest-asyncio, httpx `ASGITransport`; интеграционные требуют поднятый compose.
- Весь I/O — async; sync-библиотеки в эндпоинтах запрещены.
- Слои: `src/<domain>/{router,service,repository,schemas,models}.py`, общее — `src/core/` (config, db, redis, security, errors). Бизнес-логика не живёт в роутерах.
- Ошибки — единый формат `{"error": {"code": "...", "message": "...", "details": ...}}`, коды стабильны (контракт фронта).

## TypeScript (apps/realtime, apps/web, apps/admin)

- Node 22 LTS, **pnpm** (workspace в корне), TS strict, ESLint + Prettier (single quotes, no semi — нет; semi: true, singleQuote: true, printWidth 100).
- Типы API руками не пишутся — только генерация из `packages/contracts` (`openapi-typescript`).

## Безопасность (минимум, проверяется на ревью каждого диффа)

- Пароли: **argon2id**; ответы об ошибках auth не различают «нет юзера»/«не тот пароль».
- Access JWT 15 мин — только в памяти SPA; refresh 30 дней — httpOnly+Secure+SameSite=Lax cookie, ротация при каждом refresh, reuse detection → отзыв всей `family_id`.
- Rate limiting: Redis sliding window (Lua), обязательно на `/auth/*` и `POST /answers`.
- Валидация всех входов Pydantic/Zod; лимиты длины строк всегда; UUID — типом, не строкой.
- Эталонные ответы задач (`tasks.answer`) никогда не сериализуются в публичные схемы.
- `/internal/*` — отдельный роутер, доступ только по `INTERNAL_API_TOKEN`, в OpenAPI не публикуется.
- SQL только через ORM/параметры; raw SQL — только в миграциях и витринах статистики с параметрами.
- Заголовки: CSP, X-Content-Type-Options, X-Frame-Options=DENY, Referrer-Policy (middleware в API + Traefik в проде).

## Git

- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`), тело — по-русски.
- В `main` попадает только зелёный CI. Каждая фича — спека в `docs/specs` до кода.

## События (Kafka/Redpanda)

Топики: `answers.submitted` (key=`user_id`), `duels.finished` (key=`duel_id`), `payments.events`, `users.registered`.
Конверт: `{"v": 1, "type": "...", "occurred_at": iso8601, "payload": {...}}`. Консьюмеры идемпотентны (at-least-once).
