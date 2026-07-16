#!/usr/bin/env bash
# Backs up PostgreSQL (primary DB: users, videos, plans) and MongoDB
# (secondary storage) to timestamped, compressed dumps.
#
# Redis and Qdrant are intentionally NOT included: Redis only holds the
# Celery broker queue and transient per-video progress (safe to lose —
# in-flight jobs would need re-submitting), and Qdrant's travel-tip vectors
# are derived data that can be rebuilt from Postgres. Uploaded video files
# live in the uploads_data volume; back that up separately if you need to
# retain raw uploads (it can be large — see docs/deployment.md).
#
# Usage: ./scripts/backup.sh [backup-dir]
# Retention: BACKUP_RETENTION_DAYS (default 14) — older backups are pruned.
#
# Cron (daily at 2am):
#   0 2 * * * cd /path/to/TripClip-AI && ./scripts/backup.sh >> /var/log/tripclip-backup.log 2>&1

set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR="${1:-./backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

[[ -f .env ]] || { echo "ERROR: .env file not found. Run from the repository root."; exit 1; }
# shellcheck disable=SC1091
source .env
[[ -n "${POSTGRES_PASSWORD:-}" ]] || { echo "ERROR: POSTGRES_PASSWORD not set in .env"; exit 1; }

mkdir -p "$BACKUP_DIR"

echo "==> Backing up PostgreSQL..."
$COMPOSE exec -T postgres pg_dump -U "${POSTGRES_USER:-tripclip}" "${POSTGRES_DB:-tripclip}" \
    | gzip > "$BACKUP_DIR/postgres-$TIMESTAMP.sql.gz"
echo "    -> $BACKUP_DIR/postgres-$TIMESTAMP.sql.gz ($(du -h "$BACKUP_DIR/postgres-$TIMESTAMP.sql.gz" | cut -f1))"

echo "==> Backing up MongoDB..."
# The mongo:7 runtime image doesn't bundle mongodump/mongorestore (split out
# into mongodb-database-tools since Mongo 4.4) — use a throwaway tools
# container sharing the mongodb container's network namespace instead,
# mirroring the certbot/certbot pattern used for SSL.
docker run --rm --network container:tripclip-mongo mongodb/mongodb-database-tools \
    mongodump --host=127.0.0.1 --port=27017 --archive --db=tripclip \
    | gzip > "$BACKUP_DIR/mongo-$TIMESTAMP.archive.gz"
echo "    -> $BACKUP_DIR/mongo-$TIMESTAMP.archive.gz ($(du -h "$BACKUP_DIR/mongo-$TIMESTAMP.archive.gz" | cut -f1))"

echo "==> Pruning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "postgres-*.sql.gz" -mtime "+$RETENTION_DAYS" -print -delete
find "$BACKUP_DIR" -name "mongo-*.archive.gz" -mtime "+$RETENTION_DAYS" -print -delete

echo "==> Backup complete."
