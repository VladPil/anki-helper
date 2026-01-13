#!/bin/bash
# Остановка Docker инфраструктуры

set -e

cd "$(dirname "$0")/.."

docker compose -f .docker/docker-compose.yml --env-file .docker/configs/.env.local down "$@"
