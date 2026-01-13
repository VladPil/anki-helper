#!/bin/bash
# Запуск тестов

set -e

cd "$(dirname "$0")/.."

# Загружаем тестовые переменные
if [ -f .docker/configs/.env.test ]; then
    export $(grep -v '^#' .docker/configs/.env.test | xargs)
fi

# Запускаем pytest
uv run pytest tests/ -v "$@"
