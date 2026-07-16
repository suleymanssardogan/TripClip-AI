#!/usr/bin/env bash
# Lightweight production monitor — checks container health, disk space,
# Celery queue depth, and (optionally) the public health endpoint.
#
# Exits non-zero on any problem so it can be wired into cron mail or an
# external check-in/alerting service (healthchecks.io, cron-job monitors, etc).
# Complements Sentry (error tracking) and an external uptime monitor hitting
# /health/ready — this script covers what only the host itself can see.
#
# Usage: ./scripts/monitor.sh [yourdomain.com]
#
# Cron (every 5 min):
#   */5 * * * * cd /path/to/TripClip-AI && ./scripts/monitor.sh yourdomain.com >> /var/log/tripclip-monitor.log 2>&1

set -uo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
DOMAIN="${1:-}"
PROBLEMS=0

[[ -f .env ]] && source .env

echo "==> Container health ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
UNHEALTHY="$($COMPOSE ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null | grep -viE 'healthy|running \(healthy\)|up ')"
if [[ -n "$UNHEALTHY" ]]; then
    echo "$UNHEALTHY"
    echo "!! Unhealthy or stopped containers detected."
    PROBLEMS=1
else
    echo "    all containers up/healthy"
fi

echo "==> Disk usage"
DISK_PCT="$(df -P . | awk 'NR==2 { gsub("%","",$5); print $5 }')"
echo "    root filesystem: ${DISK_PCT}% used"
if [[ "${DISK_PCT:-0}" -ge 85 ]]; then
    echo "!! Disk usage above 85%."
    PROBLEMS=1
fi

echo "==> Celery queue depth"
QUEUE_LEN="$($COMPOSE exec -T redis redis-cli -a "${REDIS_PASSWORD:-}" --no-auth-warning LLEN video_processing 2>/dev/null || echo '?')"
echo "    video_processing queue: $QUEUE_LEN"

if [[ -n "$DOMAIN" ]]; then
    echo "==> Public readiness endpoint"
    CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMAIN/health/ready" || echo 000)"
    if [[ "$CODE" == "200" ]]; then
        echo "    /health/ready -> 200"
    else
        echo "!! /health/ready -> $CODE"
        PROBLEMS=1
    fi
fi

if [[ "$PROBLEMS" -eq 0 ]]; then
    echo "==> OK"
    exit 0
else
    echo "==> PROBLEMS DETECTED"
    exit 1
fi
