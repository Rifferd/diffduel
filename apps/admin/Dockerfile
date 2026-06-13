# DiffDuel admin SPA — сборка Vite + раздача статики через nginx.
# Сборка из корня монорепо:
#   docker build -f apps/admin/Dockerfile -t diffduel-admin .

# ---------- builder ----------
FROM node:22-alpine AS builder

RUN corepack enable

WORKDIR /app

COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY apps/admin/package.json apps/admin/
COPY packages/contracts/package.json packages/contracts/
RUN pnpm install --frozen-lockfile --filter @diffduel/admin...

COPY packages/ packages/
COPY apps/admin/ apps/admin/

ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN pnpm -C apps/admin build

# ---------- runtime ----------
FROM nginx:1.27-alpine AS runtime

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/admin/dist /usr/share/nginx/html

EXPOSE 80
