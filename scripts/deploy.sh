#!/usr/bin/env bash
# Production deploy script.
# Run from the repository root on the production server.

set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> Checking prerequisites..."
[[ -f .env ]]           || { echo "ERROR: .env file not found. Copy .env.example and fill values."; exit 1; }
[[ -d nginx/ssl ]]      || { echo "ERROR: nginx/ssl/ not found. Run scripts/setup-ssl.sh first."; exit 1; }
[[ -f nginx/ssl/fullchain.pem ]]  || { echo "ERROR: nginx/ssl/fullchain.pem missing."; exit 1; }
[[ -f nginx/ssl/privkey.pem ]]    || { echo "ERROR: nginx/ssl/privkey.pem missing."; exit 1; }

source .env
[[ -n "${JWT_SECRET_KEY:-}" ]]      || { echo "ERROR: JWT_SECRET_KEY not set in .env"; exit 1; }
[[ -n "${POSTGRES_PASSWORD:-}" ]]   || { echo "ERROR: POSTGRES_PASSWORD not set in .env"; exit 1; }
[[ -n "${REDIS_PASSWORD:-}" ]]      || { echo "ERROR: REDIS_PASSWORD not set in .env"; exit 1; }
[[ -n "${GEMINI_API_KEY:-}" ]]      || { echo "ERROR: GEMINI_API_KEY not set in .env"; exit 1; }

echo "==> Building images..."
$COMPOSE build --parallel

echo "==> Starting services..."
$COMPOSE up -d --remove-orphans

echo "==> Waiting for core-api to be healthy..."
for i in $(seq 1 30); do
    if $COMPOSE exec -T core-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
        echo "==> core-api is healthy"
        break
    fi
    echo "    waiting... ($i/30)"
    sleep 5
done

echo "==> Deployment complete."
echo "    Status: $($COMPOSE ps --format 'table {{.Name}}\t{{.Status}}')"
