FROM python:3.11-slim

# Переменные среды для оптимизации работы Python в контейнере
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Создаем непривилегированного пользователя appuser (UID 1000)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Устанавливаем зависимости Python
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем исходный код приложения
COPY --chown=appuser:appuser . .

# Делаем скрипт запуска исполняемым
RUN chmod +x /app/entrypoint.sh

# Переключаемся на непривилегированного пользователя
USER appuser

# Автоматически накатываем миграции Alembic и запускаем бота
ENTRYPOINT ["/app/entrypoint.sh"]
