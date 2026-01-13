#!/bin/bash
# Линтинг и форматирование кода

set -e

cd "$(dirname "$0")/.."

echo "Running ruff check..."
uv run ruff check src/ tests/ --fix

echo "Running ruff format..."
uv run ruff format src/ tests/

echo "Running mypy..."
uv run mypy src/
