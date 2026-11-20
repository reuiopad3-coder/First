#!/bin/sh
set -e

echo "[INFO] Применение миграций базы данных (Alembic)..."
alembic upgrade head

echo "[INFO] Запуск Telegram Stars Bot..."
exec python -m bot
