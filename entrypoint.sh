#!/bin/sh
set -e

# Создаём директории для данных и логов (на случай первого запуска без тома)
mkdir -p /app/data /app/logs

echo "[INFO] Применение миграций базы данных (Alembic)..."
alembic upgrade head

echo "[INFO] Запуск Telegram Stars Bot..."
exec python -m bot
