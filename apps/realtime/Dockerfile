# DiffDuel realtime — multi-stage prod image.
# Built from the monorepo root so the pnpm workspace + lockfile are available:
#   docker build -f apps/realtime/Dockerfile -t diffduel-realtime .

# ---------- deps: install all deps (with dev) for the realtime workspace ----------
FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /repo
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json .npmrc ./
COPY apps/realtime/package.json apps/realtime/package.json
RUN pnpm install --frozen-lockfile --filter @diffduel/realtime...

# ---------- build: компиляция TS + самодостаточный prod-набор через pnpm deploy ----------
FROM node:22-alpine AS build
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /repo
COPY --from=deps /repo /repo
COPY apps/realtime/ apps/realtime/
RUN pnpm -C apps/realtime build
# pnpm deploy собирает каталог с РЕАЛЬНЫМ плоским node_modules (без symlink в pnpm-store),
# безопасным для копирования в runtime. --legacy — стабильный режим deploy в pnpm 9.
RUN pnpm --filter @diffduel/realtime --prod --legacy deploy /app-deploy

# ---------- runtime: slim prod image ----------
FROM node:22-alpine AS runtime
ENV NODE_ENV=production APP_ENV=prod PORT=8100
WORKDIR /app
COPY --from=build /app-deploy/node_modules ./node_modules
COPY --from=build /repo/apps/realtime/dist ./dist
COPY --from=build /repo/apps/realtime/package.json ./package.json
EXPOSE 8100
USER node
CMD ["node", "dist/main.js"]
