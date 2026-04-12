# syntax=docker/dockerfile:1

# Build arguments
ARG NODE_VERSION=18
ARG ALPINE_VERSION=3.19
ARG NGINX_VERSION=1.25-alpine

# ──────────────────────────────────────────────
# Stage 1: Build — сборка frontend
# ──────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION} AS builder

WORKDIR /app

# Копирование файлов зависимостей для кэширования слоёв
COPY package.json package-lock.json* ./

# Установка зависимостей с использованием кэша
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Копирование исходного кода
COPY . .

# Сборка production-версии
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ──────────────────────────────────────────────
# Stage 2: Production — Nginx
# ──────────────────────────────────────────────
FROM nginx:${NGINX_VERSION} AS production

LABEL maintainer="remservice-planner"
LABEL org.opencontainers.image.source="https://github.com/sqfall/remservice-planner"

# Копирование собранного приложения
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

# Копирование кастомной конфигурации Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
