# syntax=docker/dockerfile:1
FROM node:20-bookworm-slim AS build

WORKDIR /app

ENV PNPM_HOME=/pnpm
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json

RUN pnpm install --frozen-lockfile

COPY . .

ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_FIREBASE_AUTH_ENABLED
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ARG NEXT_PUBLIC_FIREBASE_APP_ID
ARG NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID
ARG NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET
ARG API_PROXY_TARGET
ARG NEXT_PROXY_CLIENT_MAX_BODY_SIZE
ARG NEXT_PROXY_TIMEOUT_MS

ENV NEXT_PUBLIC_SITE_URL="${NEXT_PUBLIC_SITE_URL}" \
    NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE}" \
    NEXT_PUBLIC_FIREBASE_AUTH_ENABLED="${NEXT_PUBLIC_FIREBASE_AUTH_ENABLED}" \
    NEXT_PUBLIC_FIREBASE_API_KEY="${NEXT_PUBLIC_FIREBASE_API_KEY}" \
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN}" \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID="${NEXT_PUBLIC_FIREBASE_PROJECT_ID}" \
    NEXT_PUBLIC_FIREBASE_APP_ID="${NEXT_PUBLIC_FIREBASE_APP_ID}" \
    NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="${NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID}" \
    NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="${NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET}" \
    API_PROXY_TARGET="${API_PROXY_TARGET}" \
    NEXT_PROXY_CLIENT_MAX_BODY_SIZE="${NEXT_PROXY_CLIENT_MAX_BODY_SIZE}" \
    NEXT_PROXY_TIMEOUT_MS="${NEXT_PROXY_TIMEOUT_MS}"

RUN set -eu; \
    flag="$(printf '%s' "${NEXT_PUBLIC_FIREBASE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"; \
    case "${flag}" in \
      1|true|yes|on) \
        missing=""; \
        for key in \
          NEXT_PUBLIC_FIREBASE_API_KEY \
          NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN \
          NEXT_PUBLIC_FIREBASE_PROJECT_ID \
          NEXT_PUBLIC_FIREBASE_APP_ID \
          NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID \
          NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET; do \
          value="$(printenv "${key}" || true)"; \
          if [ -z "${value}" ]; then \
            missing="${missing} ${key}"; \
          fi; \
        done; \
        if [ -n "${missing}" ]; then \
          echo "Missing required Firebase public env at build:${missing}" >&2; \
          exit 1; \
        fi; \
        ;; \
    esac; \
    pnpm --filter @poverlay/web build && ./scripts/sync-next-standalone.sh

FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=build /app/apps/web/.next/standalone ./

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
