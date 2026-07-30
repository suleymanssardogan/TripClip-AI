#!/usr/bin/env bash
# Restores PostgreSQL and (optionally) MongoDB from backups produced by
# scripts/backup.sh.
#
# DESTRUCTIVE — overwrites current database contents. Asks for confirmation.
#
# Usage: ./scripts/restore.sh <postgres-backup.sql.gz> [mongo-backup.archive.gz]

set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
PG_BACKUP="${1:-}"
MONGO_BACKUP="${2:-}"

[[ -n "$PG_BACKUP" ]] || { echo "Usage: $0 <postgres-backup.sql.gz> [mongo-backup.archive.gz]"; exit 1; }
[[ -f "$PG_BACKUP" ]] || { echo "ERROR: $PG_BACKUP not found."; exit 1; }
[[ -f .env ]] || { echo "ERROR: .env file not found. Run from the repository root."; exit 1; }
# shellcheck disable=SC1091
source .env

echo "!! This will OVERWRITE the current database(s) with the contents of:"
echo "     Postgres: $PG_BACKUP"
if [[ -n "$MONGO_BACKUP" ]]; then
    echo "     MongoDB:  $MONGO_BACKUP"
fi
read -r -p "Type 'yes' to continue: " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { echo "Aborted."; exit 1; }

echo "==> Restoring PostgreSQL from $PG_BACKUP..."
gunzip -c "$PG_BACKUP" | $COMPOSE exec -T postgres psql -U "${POSTGRES_USER:-tripclip}" "${POSTGRES_DB:-tripclip}"

if [[ -n "$MONGO_BACKUP" ]]; then
    [[ -f "$MONGO_BACKUP" ]] || { echo "ERROR: $MONGO_BACKUP not found."; exit 1; }
    echo "==> Restoring MongoDB from $MONGO_BACKUP..."
    # See backup.sh: mongo:7 doesn't bundle mongorestore, use the tools image.
    gunzip -c "$MONGO_BACKUP" | docker run --rm -i --network container:tripclip-mongo \
        mongodb/mongodb-database-tools mongorestore --host=127.0.0.1 --port=27017 --archive --drop
fi

echo "==> Restore complete. Restart dependent services:"
echo "    $COMPOSE restart core-api celery-worker"
