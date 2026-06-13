# DiffDuel image-gen worker — prod-образ.
# Многостадийная сборка: uv ставит зависимости в venv, рантайм — slim без uv.

FROM python:3.12-slim AS builder

# uv из официального дистрибутива (быстрый, воспроизводимый lock).
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Сначала только манифесты — кэш слоёв при неизменных зависимостях.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project --frozen || uv sync --no-dev --no-install-project

# Затем код и шрифты.
COPY src ./src
COPY assets ./assets
RUN uv sync --no-dev --frozen || uv sync --no-dev


FROM python:3.12-slim AS runtime

# Pillow тянет системные либы для шрифтов/PNG (freetype, zlib уже в slim).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Непривилегированный пользователь.
RUN useradd --create-home --uid 10001 worker
WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=prod

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/assets ./assets

USER worker

# Долгоживущий консьюмер; healthcheck — живой процесс (нет HTTP-порта).
ENTRYPOINT ["python", "-m", "src.workers.image_gen"]
