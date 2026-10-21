#!/bin/sh
# Обновить сайт до последней версии из GitHub: ./deploy/update.sh
set -e
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
docker image prune -f
