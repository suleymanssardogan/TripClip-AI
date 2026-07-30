#!/usr/bin/env bash
# Generates cryptographically random secrets for production deployment.
# Pipe output into .env or use the values manually.

set -euo pipefail

echo "# Generated secrets — paste into .env"
echo "JWT_SECRET_KEY=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 64)"
echo "INTERNAL_API_SECRET=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
echo "REDIS_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
echo "GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
