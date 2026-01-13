#!/bin/bash
# Запуск сервера разработки

set -e

cd "$(dirname "$0")/.."

# Загружаем переменные окружения
if [ -f .docker/configs/.env.local ]; then
    export $(grep -v '^#' .docker/configs/.env.local | xargs)
fi

# Запускаем uvicorn
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
