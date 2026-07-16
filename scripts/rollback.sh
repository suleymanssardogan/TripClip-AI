#!/usr/bin/env bash
# Rolls back to a previous commit and redeploys.
# Takes a database backup first as a safety net before touching anything.
#
# Usage: ./scripts/rollback.sh [git-ref]   (default: HEAD~1, the previous commit)

set -euo pipefail

TARGET="${1:-HEAD~1}"
COMPOSE="docker compose -f docker-compose.prod.yml"

CURRENT_REF="$(git rev-parse --short HEAD)"
CURRENT_MSG="$(git log -1 --format=%s)"
TARGET_REF="$(git rev-parse --short "$TARGET")"
TARGET_MSG="$(git log -1 --format=%s "$TARGET")"

echo "==> Current:  $CURRENT_REF  $CURRENT_MSG"
echo "==> Target:   $TARGET_REF  $TARGET_MSG"
read -r -p "Roll back to target and redeploy? [y/N] " CONFIRM
[[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]] || { echo "Aborted."; exit 1; }

echo "==> Taking a safety backup before rollback..."
./scripts/backup.sh

echo "==> Checking out $TARGET_REF..."
git checkout "$TARGET"

cat <<'EOF'
!! NOTE: Alembic migrations auto-apply on core-api startup but are NOT
   auto-reverted by a git checkout. If the version you're rolling back to
   predates a migration that already ran against this database, downgrade
   the schema manually BEFORE redeploying, e.g.:
     docker compose -f docker-compose.prod.yml exec core-api alembic downgrade -1
   Check `alembic history` on both commits to see if this applies.
EOF
read -r -p "Continue with redeploy now? [y/N] " CONFIRM2
[[ "$CONFIRM2" == "y" || "$CONFIRM2" == "Y" ]] || { echo "Stopped after checkout. Run ./scripts/deploy.sh manually when ready."; exit 0; }

./scripts/deploy.sh

echo "==> Rollback complete. Verify with: ./scripts/smoke-test.sh <yourdomain.com>"
