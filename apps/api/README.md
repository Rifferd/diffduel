# DiffDuel Core API

Ядро REST API проекта DiffDuel: аутентификация (JWT + ротация refresh-токенов),
профиль пользователя, темы, внутренний роутер для realtime-сервиса.

Стек: Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, Redis,
argon2id, PyJWT, structlog. Менеджер пакетов — **uv**.

## Требования

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Поднятый dev-стек инфраструктуры (PostgreSQL 16 и Redis 7).

Поднять инфраструктуру из корня монорепо:

```bash
docker compose -f infra/compose/docker-compose.yml up -d postgres redis
```

Учётки dev (см. `docs/specs/conventions.md`): PostgreSQL `diffduel/diffduel`,
база `diffduel`, порт `5432`; Redis без пароля, порт `6379`.

## Установка

```bash
cd apps/api
uv sync --extra dev
```

Скопируйте эталон переменных окружения и при необходимости поправьте:

```bash
cp .env.example .env
```

Ключевые переменные (имена едины для всего монорепо):

| Переменная | Назначение |
|---|---|
| `APP_ENV` | `dev` / `test` / `prod` (в `prod` cookie выставляются с `Secure`) |
| `DATABASE_URL` | `postgresql+asyncpg://diffduel:diffduel@localhost:5432/diffduel` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `JWT_SECRET` | секрет подписи access-JWT (>=32 символов; в проде — длинный случайный) |
| `ACCESS_TOKEN_TTL` / `REFRESH_TOKEN_TTL` | TTL токенов в секундах (900 / 2592000) |
| `INTERNAL_API_TOKEN` | токен доступа к `/internal/*` |
| `CORS_ORIGINS` | список origin'ов через запятую |

## Миграции (Alembic)

Применить все миграции к БД из `DATABASE_URL`:

```bash
uv run alembic upgrade head
```

Откат на одну ревизию / в ноль:

```bash
uv run alembic downgrade -1
uv run alembic downgrade base
```

Initial-миграция создаёт расширения `citext` и `pgcrypto`, все native enum'ы,
все таблицы модели данных (§5 ТЗ), а также партиционированную таблицу `answers`
(`PARTITION BY RANGE (submitted_at)`) с партициями на текущий и следующий месяц
и функцией-хелпером `create_answers_partition(date)` для создания новых партиций.

## Запуск

```bash
uv run uvicorn src.main:app --reload --port 8000
```

- Документация OpenAPI: <http://localhost:8000/docs>
- Health-check (проверяет PostgreSQL и Redis): <http://localhost:8000/healthz>

Внутренний роутер `/internal/*` в публичный OpenAPI не попадает; доступ — строго
по заголовку `X-Internal-Token`, равному `INTERNAL_API_TOKEN`.

## Тесты

Тестам нужны поднятые PostgreSQL и Redis. Тестовая база `diffduel_test` и
тестовая БД Redis (`/15`) создаются и мигрируются автоматически в фикстурах.

```bash
uv run pytest
```

Покрытие: unit-тесты криптопримитивов (argon2, JWT, sha256 refresh) и
Lua-rate-limit на реальном Redis; интеграционный auth-флоу (register → login →
me → ротация refresh → reuse detection с отзывом family → logout), 409 на
дубликат email, 429 на rate limit, видимость `/internal` в OpenAPI, security-заголовки.

## Контроль качества (Definition of Done)

```bash
uv run ruff check
uv run ruff format --check
uv run mypy src
uv run pytest
```

Все четыре команды должны проходить без ошибок.

## Структура

```
src/
  core/            конфиг, БД, Redis, security, errors, logging, rate_limit,
                   middleware, exception_handlers, enums, db_types
  auth/            register/login/refresh/logout, refresh-токены, JWT-зависимости
  users/           GET/PATCH /me, модели users + ratings
  topics/          GET /topics, модели topics + tasks + task_stats
  internal_api/    /internal/* (заглушка ping, X-Internal-Token)
  duels/           модели duels + answers (партиционированная)
  billing/         модели subscriptions + payments
  tournaments/     модели tournaments + tournament_entries
  main.py          app factory, /healthz, middleware, CORS, обработчики ошибок
migrations/        Alembic (async) + initial-миграция
tests/             pytest + httpx ASGITransport
```

Слои внутри домена: `router` (HTTP) → `service` (бизнес-логика) →
`repository` (доступ к данным); `schemas` (Pydantic), `models` (SQLAlchemy).
