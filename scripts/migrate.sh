#!/bin/bash
# Запуск миграций базы данных

set -e

cd "$(dirname "$0")/.."

# Загружаем переменные окружения
if [ -f .docker/configs/.env.local ]; then
    export $(grep -v '^#' .docker/configs/.env.local | xargs)
fi

# Применяем миграции
uv run alembic upgrade head
