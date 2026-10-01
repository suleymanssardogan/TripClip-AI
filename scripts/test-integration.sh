#!/usr/bin/env bash
# Only the disposable integration project is created or removed.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! docker info >/dev/null 2>&1; then
  echo "Integration tests require a running Docker engine." >&2
  exit 1
fi
export COMPOSE_PROJECT_NAME="tripclip-integration-$$"
compose=(docker compose -f docker-compose.integration.yml)
mkdir -p integration-reports
cleanup() {
  "${compose[@]}" logs --no-color > integration-reports/services.log 2>&1 || true
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from runner
