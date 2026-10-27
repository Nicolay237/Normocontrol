#!/bin/sh
# Обновить сайт до последней версии из GitHub: ./deploy/update.sh
set -e
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
# Caddy не перечитывает Caddyfile сам — подхватить изменения без остановки сайта
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile || true
docker image prune -f
