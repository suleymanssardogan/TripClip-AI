#!/usr/bin/env bash
# Sets the production domain in nginx/nginx.conf (replaces the CHANGEME
# placeholder). Run once during first-time setup, before scripts/setup-ssl.sh.
#
# Usage: ./scripts/configure-domain.sh yourdomain.com

set -euo pipefail

DOMAIN="${1:-}"
[[ -n "$DOMAIN" ]] || { echo "Usage: $0 <domain>"; exit 1; }

CONF="nginx/nginx.conf"
[[ -f "$CONF" ]] || { echo "ERROR: $CONF not found. Run from the repository root."; exit 1; }

sed -i.bak "s/CHANGEME\.example\.com/$DOMAIN/g" "$CONF"
rm -f "$CONF.bak"

echo "==> $CONF now serves:"
grep -n "server_name" "$CONF"
