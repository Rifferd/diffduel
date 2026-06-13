# DiffDuel Core API — multi-stage prod image (uv).
# Сборка из корня монорепо:
#   docker build -f apps/api/Dockerfile -t diffduel-api .

# ---------- builder: ставит зависимости в .venv ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app/apps/api

# Сначала только манифесты — слой кэшируется, пока не меняются зависимости.
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/ ./
RUN uv sync --frozen --no-dev

# ---------- runtime: только venv + код, без uv и тулчейна ----------
FROM python:3.12-slim AS runtime

# Непривилегированный пользователь.
RUN useradd --create-home --uid 10001 app

WORKDIR /app/apps/api

COPY --from=builder --chown=app:app /app/apps/api /app/apps/api

ENV PATH="/app/apps/api/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# Прод: без reload, воркеры масштабируются на уровне compose/оркестратора.
# Миграции прогоняются отдельным шагом деплоя (release-команда), не в CMD.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
