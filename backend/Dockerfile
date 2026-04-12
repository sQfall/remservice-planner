# syntax=docker/dockerfile:1

# Build arguments
ARG PYTHON_VERSION=3.11
ARG ALPINE_VERSION=3.19

# ──────────────────────────────────────────────
# Stage 1: Build — установка зависимостей
# ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

WORKDIR /app

# Установка системных зависимостей для сборки
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    && rm -rf /var/cache/apk/*

# Копирование файла зависимостей первым слоем для кэширования
COPY requirements.txt .

# Установка Python-зависимостей в отдельную директорию
RUN pip install --no-compile --prefix=/install -r requirements.txt

# ──────────────────────────────────────────────
# Stage 2: Production — минимальный образ
# ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS production

LABEL maintainer="remservice-planner"
LABEL org.opencontainers.image.source="https://github.com/sqfall/remservice-planner"

# Создание непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Копирование Python-зависимостей из builder
COPY --from=builder --chown=appuser:appuser /install/lib/python*/site-packages /usr/local/lib/python*/site-packages
COPY --from=builder --chown=appuser:appuser /install/bin /usr/local/bin

# Копирование приложения
COPY --chown=appuser:appuser . .

# Создание директории для БД с правильными правами
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REMSERVICE_DATABASE_URL=sqlite+aiosqlite:///./data/data.db \
    REMSERVICE_DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Переключение на непривилегированного пользователя
USER appuser

EXPOSE 8000

# Запуск через uvicorn production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
