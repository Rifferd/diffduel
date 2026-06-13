# Runbook: первый деплой DiffDuel на VPS

> Применяется один раз при подключении нового VPS (2 vCPU / 4 GB, Ubuntu 22.04+).
> Все артефакты уже в репозитории; здесь — последовательность действий.

## 0. Что нужно от владельца заранее

- VPS с публичным IP, root или sudo-доступ по SSH.
- DNS-записи (A) указывают на IP VPS: `diffduel.com`, `www.diffduel.com`, `admin.diffduel.com`, `cdn.diffduel.com`.
- GitHub Secrets в репозитории (Settings → Secrets → Actions, окружение `production`):
  `SSH_HOST`, `SSH_USER`, `SSH_KEY` (приватный ключ деплой-пользователя), `GHCR_OWNER` (= `rifferd`, нижним регистром).

## 1. Подготовка сервера

```bash
# Docker + compose-plugin
curl -fsSL https://get.docker.com | sh
# деплой-пользователь (не root) в группе docker
adduser --disabled-password deploy && usermod -aG docker deploy
# публичный ключ деплоя — в ~deploy/.ssh/authorized_keys
mkdir -p /opt/diffduel && chown deploy:deploy /opt/diffduel
```

## 2. Код и секреты на сервере

```bash
sudo -iu deploy
git clone https://github.com/Rifferd/diffduel.git /opt/diffduel
cd /opt/diffduel/infra/compose
cp .env.prod.example .env.prod
# Сгенерировать и вписать секреты:
openssl rand -hex 64   # → JWT_SECRET
openssl rand -hex 32   # → INTERNAL_API_TOKEN, POSTGRES_PASSWORD, S3_SECRET_KEY
# Проверить DOMAIN, ACME_EMAIL, GHCR_OWNER, DATABASE_URL (пароль = POSTGRES_PASSWORD).
nano .env.prod
chmod 600 .env.prod
```

## 3. Первый запуск

Лучше — через CI: запушить в `main` (или `workflow_dispatch` на `deploy.yml`); workflow соберёт образы, запушит в GHCR, прогонит миграции, поднимет стек, сделает smoke.

Ручной вариант (если CI ещё не настроен):
```bash
cd /opt/diffduel/infra/compose
docker login ghcr.io                       # PAT с read:packages
export IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## 4. Бутстрап контента и админа

```bash
# 150 quiz-задач + темы
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api python -m src.seeds
# первый администратор (пароль спросит интерактивно)
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm \
  -e ADMIN_PASSWORD api python -m src.create_admin --email you@diffduel.com --username founder
```

## 5. Проверка

```bash
curl -fsS https://diffduel.com/api/healthz          # {"status":"ok",...}
curl -fsS https://diffduel.com/socket/healthz        # realtime
# открыть https://diffduel.com (SPA), https://admin.diffduel.com (логин founder)
docker compose -f docker-compose.prod.yml ps         # все healthy
docker stats --no-stream                             # суммарно < 4G
```

## 6. Дальнейшие деплои

Автоматически: push в `main` → CI зелёный → `deploy.yml` собирает образы с тегом `git sha`, пуллит, мигрирует, поднимает, smoke, откат при фейле.

## Откат вручную

```bash
export IMAGE_TAG=<предыдущий git sha>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## Бэкап PG (см. ADR-0003)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T postgres \
  pg_dump -U diffduel diffduel | gzip > /opt/diffduel/backups/$(date +%F).sql.gz
# выгрузка в MinIO bucket exports + еженедельно во внешнее хранилище
```
