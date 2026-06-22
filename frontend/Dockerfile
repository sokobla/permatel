# ─────────────────────────────────────────────────────────────────────────────
# PERMATEL — Frontend (production)
# Build Vite → service de fichiers statiques par Nginx (non-root, durci).
# L'API est servie en same-origin via le proxy Nginx (/api, /uploads).
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1 : build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
# Couche de cache des dépendances
COPY package*.json ./
RUN npm ci

COPY . .
# API same-origin : les appels passent par le proxy Nginx (/api)
ARG VITE_API_BASE_URL=/api
ARG VITE_APP_NAME=PERMATEL
ARG VITE_APP_VERSION=1.4.0
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_APP_NAME=$VITE_APP_NAME \
    VITE_APP_VERSION=$VITE_APP_VERSION
RUN npm run build


# ── Stage 2 : runtime Nginx ───────────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Image "unprivileged" : tourne en uid 101, écoute sur 8080 (non-root).
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1
