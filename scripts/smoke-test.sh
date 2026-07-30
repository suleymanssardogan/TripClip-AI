#!/usr/bin/env bash
# Post-deployment smoke test — verifies the stack is reachable and correctly
# routed from the OUTSIDE, the way a real client (browser or the iOS app)
# would see it. Run this after every deploy/rollback before calling it done.
#
# Usage: ./scripts/smoke-test.sh yourdomain.com

set -uo pipefail

DOMAIN="${1:-}"
[[ -n "$DOMAIN" ]] || { echo "Usage: $0 <domain>"; exit 1; }

BASE="https://$DOMAIN"
FAIL=0

check_status() {
    local name="$1" method="$2" url="$3" expect="$4"
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X "$method" "$url" || echo 000)"
    if [[ "$code" == "$expect" ]]; then
        echo "  OK   $name ($code)"
    else
        echo "  FAIL $name (got $code, expected $expect)"
        FAIL=1
    fi
}

echo "==> Smoke testing $BASE"

check_status "HTTP redirects to HTTPS"        GET "http://$DOMAIN/"           301
check_status "Web app loads"                  GET "$BASE/"                    200
check_status "Web BFF health (via nginx)"     GET "$BASE/health"              200
check_status "Mobile BFF health (via nginx)"  GET "$BASE/health/mobile"       200

# Hitting a real route with a deliberately empty body proves the request makes
# it all the way through nginx -> BFF -> FastAPI routing (422, not 502/404).
check_status "Web BFF routes live"    POST "$BASE/api/web/auth/login"    422
check_status "Mobile BFF routes live" POST "$BASE/api/mobile/auth/login" 422

echo "==> TLS certificate"
EXPIRY="$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
if [[ -n "$EXPIRY" ]]; then
    echo "  OK   cert valid, expires: $EXPIRY"
else
    echo "  FAIL could not read TLS certificate"
    FAIL=1
fi

if [[ "$FAIL" -eq 0 ]]; then
    echo "==> All smoke tests passed."
    exit 0
else
    echo "==> SMOKE TESTS FAILED — do not consider this deployment verified."
    exit 1
fi
