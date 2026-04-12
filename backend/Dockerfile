# syntax=docker/dockerfile:1

# Build arguments
ARG PYTHON_VERSION=3.11-slim

# ──────────────────────────────────────────────
# Stage 1: Build — установка зависимостей
# ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

WORKDIR /app

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование файла зависимостей первым слоем для кэширования
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# ──────────────────────────────────────────────
# Stage 2: Production — минимальный образ
# ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS production

LABEL maintainer="remservice-planner"
LABEL org.opencontainers.image.source="https://github.com/sqfall/remservice-planner"

# Системные шрифты для кириллицы в PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Создание непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Копирование Python-зависимостей из builder
COPY --from=builder --chown=appuser:appuser /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appuser /usr/local/bin /usr/local/bin

# Копирование приложения
COPY --chown=appuser:appuser . .

# Создание пустого файла БД и выдача прав на директорию
RUN touch /app/data.db && chown -R appuser:appuser /app

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REMSERVICE_DATABASE_URL=sqlite+aiosqlite:///./data.db \
    REMSERVICE_DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Переключение на непривилегированного пользователя
USER appuser

EXPOSE 8000

# Запуск через uvicorn production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
