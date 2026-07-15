#!/usr/bin/env bash
# Obtains a Let's Encrypt certificate and installs it for nginx.
# Run this once on the production server before deploying.
#
# Usage: ./scripts/setup-ssl.sh yourdomain.com your@email.com

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

[[ -n "$DOMAIN" ]] || { echo "Usage: $0 <domain> <email>"; exit 1; }
[[ -n "$EMAIL" ]]  || { echo "Usage: $0 <domain> <email>"; exit 1; }

SSL_DIR="nginx/ssl"
mkdir -p "$SSL_DIR"

echo "==> Obtaining certificate for $DOMAIN..."

# Temporarily serve ACME challenge via a standalone server (port 80 must be free)
docker run --rm \
    -p 80:80 \
    -v "$(pwd)/$SSL_DIR:/etc/letsencrypt/live/$DOMAIN" \
    certbot/certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --domains "$DOMAIN" \
    --cert-path "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" \
    --key-path "/etc/letsencrypt/live/$DOMAIN/privkey.pem"

echo "==> Certificate installed to $SSL_DIR/"
echo "    Update nginx/nginx.conf: replace CHANGEME.example.com with $DOMAIN"
echo "    Then run: ./scripts/deploy.sh"
