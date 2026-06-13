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

# ---------- build: compile TypeScript to dist ----------
FROM node:22-alpine AS build
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /repo
COPY --from=deps /repo /repo
COPY apps/realtime/ apps/realtime/
RUN pnpm -C apps/realtime build \
  && pnpm install --prod --frozen-lockfile --filter @diffduel/realtime...

# ---------- runtime: slim prod image ----------
FROM node:22-alpine AS runtime
ENV NODE_ENV=production APP_ENV=prod PORT=8100
WORKDIR /app
# Bring prod node_modules + compiled output only.
COPY --from=build /repo/apps/realtime/node_modules ./node_modules
COPY --from=build /repo/node_modules ./root_node_modules
COPY --from=build /repo/apps/realtime/dist ./dist
COPY --from=build /repo/apps/realtime/package.json ./package.json
# Hoisted deps live at the repo root in a pnpm workspace; expose them too.
ENV NODE_PATH=/app/node_modules:/app/root_node_modules
EXPOSE 8100
USER node
CMD ["node", "dist/main.js"]
