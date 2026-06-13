# DiffDuel web SPA — сборка Vite + раздача статики через nginx.
# Сборка из корня монорепо (нужен pnpm workspace + lockfile):
#   docker build -f apps/web/Dockerfile -t diffduel-web .

# ---------- builder ----------
FROM node:22-alpine AS builder

RUN corepack enable

WORKDIR /app

# Манифесты воркспейса — слой кэшируется, пока не меняются зависимости.
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY apps/web/package.json apps/web/
COPY packages/contracts/package.json packages/contracts/
RUN pnpm install --frozen-lockfile --filter @diffduel/web...

# Исходники. design-system нужен как @ds-alias на этапе сборки CSS.
COPY packages/ packages/
COPY apps/web/ apps/web/

# VITE_* подставляются на этапе сборки (прод-домены задаёт деплой через build-args).
ARG VITE_API_URL=/api
ARG VITE_REALTIME_URL=/
ENV VITE_API_URL=$VITE_API_URL VITE_REALTIME_URL=$VITE_REALTIME_URL
RUN pnpm -C apps/web build

# ---------- runtime: nginx со статикой ----------
FROM nginx:1.27-alpine AS runtime

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80
