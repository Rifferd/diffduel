# DiffDuel — арена дуэлей для разработчиков

> **diffduel.com** · by **Rifferd** · построен в режиме **AI-only development** (Claude Code)

Два игрока получают одинаковый набор задач (SQL, баг в JS, конкурентность, mini system design) и решают на скорость и точность в реальном времени. Соло-тренировки, рейтинг Эло, лидерборды, турниры.

## Монорепо

```
apps/
  api/        Core API — Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic
  realtime/   Дуэли и матчмейкинг — TypeScript, NestJS, Socket.IO + Redis adapter
  workers/    Фоновые задачи и Kafka-консьюмеры — share-карточки, аналитика, антифрод
  web/        Основная SPA — Vue 3 + Vite + Pinia + TanStack Query (+ PWA)
  admin/      Админка — React 18 + Vite + TanStack Table/Query
  bot/        Telegram-бот — aiogram
packages/
  contracts/      OpenAPI + AsyncAPI, сгенерированные TS-клиенты
  ui-tokens/      Дизайн-токены — единый источник для web/admin/share-карточек
  design-system/  Дизайн-код (read-only контракт): стайлгайд + 25 свёрстанных страниц
infra/
  compose/    docker compose: dev-стек (PG, Redis, Redpanda, MinIO, observability)
  deploy/     Traefik, скрипты деплоя на VPS
  grafana/    дашборды как код
docs/
  adr/        Architecture Decision Records
  specs/      спецификации фич — вход для AI-разработки
  ai-log/     журнал AI-only процесса: спека → промпт → дифф → тесты
```

## Стек (кратко)

PostgreSQL 16 · Redis 7 · Kafka (Redpanda) · MinIO (S3) · FastAPI · NestJS/Socket.IO · Vue 3 · React 18 · OpenTelemetry → Grafana/Tempo/Loki/Prometheus · GitHub Actions · Traefik + TLS.

Обоснование каждого выбора — в [`base_/TZ_DiffDuel.md`](base_/TZ_DiffDuel.md) (§3) и в ADR.

## Запуск (dev)

```bash
docker compose -f infra/compose/docker-compose.yml up -d   # инфраструктура
# дальше — см. README конкретного приложения в apps/*
```

## AI-only development

Весь проект разрабатывается через Claude Code и это документируется публично: каждая фича проходит путь **спека (`docs/specs`) → промпт → дифф → линтеры и тесты → ревью → ADR (`docs/adr`)**. Журнал процесса — в [`docs/ai-log/`](docs/ai-log/).

## Лицензия

Исходный код опубликован для прозрачности и портфолио. Все права защищены © Rifferd. Использование кода и контента в коммерческих целях без письменного разрешения запрещено.
