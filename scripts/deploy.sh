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

# Compose parses dotenv itself; never execute its contents as shell code.
$COMPOSE config --quiet
python3 scripts/check-production.py

if grep -q 'CHANGEME.example.com' nginx/nginx.conf; then
    echo "ERROR: Configure nginx domain before deployment."
    exit 1
fi

echo "==> Building images..."
$COMPOSE build --parallel

echo "==> Starting services..."
$COMPOSE up -d --remove-orphans --wait --wait-timeout 300

# Liveness alone does not prove the database and broker are available.
$COMPOSE exec -T core-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=30)"

echo "==> Deployment complete."
echo "    Status: $($COMPOSE ps --format 'table {{.Name}}\t{{.Status}}')"
echo "    Next:   ./scripts/smoke-test.sh yourdomain.com"
