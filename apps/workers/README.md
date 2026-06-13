# DiffDuel workers — image-gen

Фоновый воркер генерации share-карточек дуэлей (ТЗ §4 шаг 6, §13;
`docs/specs/leaderboards-admin.md` раздел C).

## Что делает

Консьюмер топика Kafka/Redpanda **`duels.finished`** (group `image-gen`,
at-least-once). Для каждого события:

1. **Идемпотентность.** Запрашивает у Core API
   `GET /internal/duels/{id}/card`. Если у дуэли уже есть `share_card_key` —
   событие пропускается (повторная доставка / повторный рендер не делаются).
2. **Рендер карточки** (Pillow, чистая функция `render_card`): PNG **1200×630**
   (OG-формат). Диагональный VS-сплит — зелёная половина победителя
   (`--share-plus`), красная проигравшего (`--share-minus`), ничья — нейтральные
   серые (`--share-draw-*`). Ник победителя, счёт и дельты Эло (`+24` / `−18`) —
   **моноширинным** шрифтом. Обязательный водяной знак `diffduel.com` в углу.
3. **Upload** в MinIO bucket `share-cards` (public-read), ключ `{duel_id}.png`,
   `Content-Type: image/png`.
4. **Запись ключа**: `POST /internal/duels/{id}/share-card {key}` с заголовком
   `X-Internal-Token` (таймаут + ретраи, как у realtime internal-client).

### Устойчивость

- Offset коммитится **только после** успешной обработки/пропуска батча
  (at-least-once — лучше повторить, чем потерять).
- Ошибка рендера/аплоада одного события не роняет консьюмер: до
  `PROCESS_MAX_ATTEMPTS` ретраев; после — лог `error` и пропуск «ядовитого»
  сообщения (защита от вечного зависания), offset двигается дальше.
- Брокер недоступен на старте — переподключение с экспоненциальным бэкоффом.

## Запуск (dev)

```bash
cd apps/workers
uv sync
cp .env.example .env        # при необходимости поправить
uv run python -m src.workers.image_gen
```

Требует поднятый compose-стек (Redpanda :19092, MinIO :9000 bucket `share-cards`,
Core API :8000).

## Переменные окружения

Полный список — в `.env.example`. Имена единые по `docs/specs/conventions.md`:
`APP_ENV`, `KAFKA_BROKERS`, `KAFKA_GROUP_ID`, `KAFKA_TOPIC`, `S3_ENDPOINT`,
`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `S3_BUCKET_SHARE_CARDS`,
`CORE_API_URL`, `INTERNAL_API_TOKEN`, `PROCESS_MAX_ATTEMPTS`.

В `APP_ENV=prod` старт падает (fail-fast), если оставлены dev-секреты
(`INTERNAL_API_TOKEN`, `S3_SECRET_KEY`).

## Шрифты

В `assets/fonts` лежат шрифты **DejaVu** (моноширинный `DejaVuSansMono` для цифр,
`DejaVuSans-Bold` для ников). Выбор и лицензия — см. `assets/fonts/LICENSE.md`.
Спека допускает JetBrains Mono + Archivo; DejaVu взят как заведомо свободно
распространяемый шрифт без сетевой загрузки при сборке (требование «моноширинный
для цифр» выполнено). Замена тривиальна — положить TTF и обновить `_FONT_*` в
`src/workers/render.py`.

## Проверки (DoD)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Юнит-тесты не требуют брокера/MinIO. Kafka/S3-интеграция помечается маркерами
`kafka` / `s3` и пропускается без стенда.

## Docker

```bash
docker build -t diffduel-image-gen .
```

Многостадийный образ `python:3.12-slim` + uv; рантайм без uv,
непривилегированный пользователь, entrypoint `python -m src.workers.image_gen`.
```
