#!/bin/sh
# Резервная копия базы в backups/ (хранятся 14 дней). В cron — раз в сутки:
#   0 4 * * * /opt/normocontrol/deploy/backup.sh
# Восстановление: gunzip -c backups/db-ДАТА.sql.gz | docker compose exec -T db psql -U normocontrol normocontrol
set -e
cd "$(dirname "$0")/.."
mkdir -p backups
docker compose exec -T db pg_dump -U normocontrol normocontrol | gzip > "backups/db-$(date +%F).sql.gz"
find backups -name 'db-*.sql.gz' -mtime +14 -delete
