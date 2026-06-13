# ADR-0003: Деплой, маршрутизация и бэкапы

- **Статус:** принято (применение ждёт VPS)
- **Дата:** 2026-06-13
- **Связано с:** ADR-0001 (выбор VPS 2 vCPU / 4 GB)

## Контекст

Нужен прод-деплой полного стека (api, realtime, workers, web, admin + PG/Redis/Redpanda/MinIO) на выделенный VPS 2 vCPU / 4 GB с TLS, маршрутизацией и автоматическим выкатом из CI. Память ограничена — нужны явные лимиты и однопоточные брокеры.

## Решение

**Reverse proxy — Traefik v3** (а не nginx): нативная интеграция с Docker-лейблами (роуты описаны рядом с сервисом в compose), Let's Encrypt из коробки, sticky-cookie для WebSocket. HTTP→HTTPS редирект глобально.

**Маршрутизация по одному домену + поддомены:**
- `diffduel.com`, `www.diffduel.com` → web SPA (priority 1 — ловит всё незанятое).
- `diffduel.com/api/*` → Core API (StripPrefix `/api`).
- `diffduel.com/socket/*` → realtime (sticky cookie `dd_rt`).
- `admin.diffduel.com` → admin SPA (отдельный поддомен — нет проблем с base-path).
- `cdn.diffduel.com` → MinIO (публичная раздача share-карточек).

Фронты собираются с `VITE_API_URL=/api`, `VITE_REALTIME_URL=/` (один origin → нет CORS-проблем в браузере, cookie refresh работает на том же домене).

**Образы:** multi-stage, в GHCR (`ghcr.io/<owner>/diffduel-<svc>`). Python — uv в builder, runtime без тулчейна, непривилегированный user. Фронты — node-сборка → nginx:alpine со статикой и SPA history-fallback.

**Память (лимиты в compose, сумма ~3.3 GB из 4):** pg 768M, redpanda 600M (`--smp=1 --memory=512M`), api 512M, realtime 512M, workers 384M, redis 256M (maxmemory 200mb, `noeviction` — лидерборды/состояние дуэлей терять нельзя), minio 256M, traefik 128M, web/admin по 64M. Остаток — ОС и пики.

**Деплой (`.github/workflows/deploy.yml`):** после зелёных CI (workflow_run) build+push образов с тегом `git sha` → SSH на VPS → `compose pull` → `alembic upgrade head` (release-шаг до перезапуска) → `up -d` → smoke `/healthz` → откат на `latest` при фейле. Workflow безопасно no-op'ит, пока не заданы секреты `SSH_HOST/SSH_USER/SSH_KEY/GHCR_OWNER` (VPS ещё не куплен).

**Бэкапы (RPO 24ч, ТЗ §8):** ночной `pg_dump` в bucket `exports` MinIO + еженедельная выгрузка дампа во внешнее хранилище (вне VPS — на случай потери сервера). Реализация — cron-таска воркера или системный cron на хосте; раз в месяц — проверка восстановления на отдельную БД. Команда восстановления и расписание документируются при подключении VPS.

## Последствия

- (+) Роуты, TLS и sticky WS — декларативно в одном compose; добавить сервис = добавить лейблы.
- (+) Образы проверены локально (api `/healthz` 200, web SPA-fallback 200) — деплой не упрётся в кривой Dockerfile.
- (−) Всё на одном узле: падение VPS = полный даунтайм. Для текущей стадии (≤200 онлайн) приемлемо; HA — отдельное решение при росте.
- (−) `noeviction` у Redis: при упоре в 200mb запись начнёт отвергаться — нужен алерт на использование памяти Redis.
- При росте — вертикальный апгрейд тарифа (ADR-0001) либо вынос PG/брокера на управляемый сервис.
