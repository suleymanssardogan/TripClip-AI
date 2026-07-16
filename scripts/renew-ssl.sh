#!/usr/bin/env bash
# Renews the Let's Encrypt certificate WITHOUT stopping nginx (webroot method).
# Unlike scripts/setup-ssl.sh (standalone, used once before the stack is up),
# this assumes nginx is already running and serving :80 — it answers the ACME
# challenge through nginx's /.well-known/acme-challenge/ location instead of
# binding port 80 itself.
#
# Safe to run repeatedly / on a schedule: --keep-until-expiring skips the
# request entirely unless the certificate is within 30 days of expiry.
#
# Usage: ./scripts/renew-ssl.sh yourdomain.com your@email.com
#
# Cron (daily, recommended by Let's Encrypt):
#   0 3 * * * cd /path/to/TripClip-AI && ./scripts/renew-ssl.sh yourdomain.com admin@yourdomain.com >> /var/log/tripclip-ssl-renew.log 2>&1

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

[[ -n "$DOMAIN" ]] || { echo "Usage: $0 <domain> <email>"; exit 1; }
[[ -n "$EMAIL" ]]  || { echo "Usage: $0 <domain> <email>"; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml"
WEBROOT="$(pwd)/nginx/certbot-webroot"
mkdir -p "$WEBROOT"

if ! $COMPOSE ps nginx --format '{{.Status}}' 2>/dev/null | grep -qi "up"; then
    echo "ERROR: nginx is not running. This script renews via the running nginx's"
    echo "       ACME challenge location — start the stack first (./scripts/deploy.sh)."
    exit 1
fi

echo "==> Checking/renewing certificate for $DOMAIN via webroot..."
docker run --rm \
    -v "$WEBROOT:/var/www/certbot" \
    -v "$(pwd)/nginx/ssl:/etc/letsencrypt/live/$DOMAIN" \
    certbot/certbot certonly \
    --webroot -w /var/www/certbot \
    --non-interactive \
    --agree-tos \
    --keep-until-expiring \
    --email "$EMAIL" \
    --domains "$DOMAIN" \
    --cert-path "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" \
    --key-path "/etc/letsencrypt/live/$DOMAIN/privkey.pem"

echo "==> Reloading nginx to pick up any renewed certificate..."
$COMPOSE exec -T nginx nginx -s reload

echo "==> Done."
