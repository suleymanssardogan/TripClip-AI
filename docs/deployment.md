# Deployment Guide

## Prerequisites

- Ubuntu 22.04+ server (minimum 4GB RAM, 40GB disk)
- Docker 24+ and Docker Compose plugin installed
- Domain name with A record pointing to the server IP
- Port 80 and 443 open in the firewall
- Outbound internet access for the server itself — `scripts/setup-ssl.sh`, `scripts/renew-ssl.sh`, and `scripts/backup.sh` pull small helper images on demand (`certbot/certbot`, `mongodb/mongodb-database-tools`, `alpine`)

## First-Time Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/TripClip-AI.git
cd TripClip-AI
```

### 2. Configure environment

```bash
cp .env.example .env
```

Generate secrets:
```bash
./scripts/generate-secrets.sh >> .env
```

Open `.env` and fill in the required values:
- `JWT_SECRET_KEY` — already generated
- `POSTGRES_PASSWORD` — already generated
- `REDIS_PASSWORD` — already generated
- `GEMINI_API_KEY` — from Google AI Studio (aistudio.google.com)
- `SENTRY_DSN` — optional, from sentry.io

### 3. Obtain SSL certificate

```bash
./scripts/setup-ssl.sh yourdomain.com admin@yourdomain.com
```

This starts a temporary HTTP server to complete the Let's Encrypt ACME challenge, then places the certificates in `nginx/ssl/`.

### 4. Update nginx domain

```bash
./scripts/configure-domain.sh yourdomain.com
```

Or manually: open `nginx/nginx.conf` and replace `CHANGEME.example.com` with your domain:
```nginx
server_name yourdomain.com;
```

### 5. Deploy

```bash
./scripts/deploy.sh
```

The script validates the environment, builds all images, starts services, and waits for health checks.

---

## Updating

```bash
git pull
./scripts/deploy.sh
```

The deploy script uses `--remove-orphans` to clean up old containers.

---

## SSL Renewal

Let's Encrypt certificates expire every 90 days.

- `scripts/setup-ssl.sh` is for **first-time issuance only** — it binds port 80 itself (standalone mode), which requires nginx to not be running yet.
- `scripts/renew-ssl.sh` is for **renewal** — it answers the ACME challenge through nginx's `/.well-known/acme-challenge/` location (webroot mode, added in `nginx/nginx.conf`), so nginx keeps serving traffic the whole time. Re-running it is always safe: `--keep-until-expiring` makes it a no-op unless the cert is within 30 days of expiry.

Add a daily cron job (Let's Encrypt's own recommendation is to check daily, not just monthly):

```bash
# /etc/cron.d/tripclip-ssl
0 3 * * * root cd /path/to/TripClip-AI && ./scripts/renew-ssl.sh yourdomain.com admin@yourdomain.com >> /var/log/tripclip-ssl-renew.log 2>&1
```

---

## Health Checks

Every service in `docker-compose.prod.yml` has a container-level `healthcheck` (nginx, web, core-api, celery-worker, web-bff, mobile-bff, postgres, redis, mongodb) — `docker compose ps` shows `(healthy)`/`(unhealthy)` per container, and nginx will not start routing traffic until web, web-bff, and mobile-bff report healthy.

Externally reachable endpoints (through nginx):

| Endpoint | Expected |
|----------|----------|
| `GET /health` | `{"status":"healthy"}` — web-bff |
| `GET /health/mobile` | `{"status":"healthy"}` — mobile-bff |
| `GET /health/ready` | `{"status":"ready","checks":{"postgres":"ok","redis":"ok"}}` — core-api, proxied at the BFF layer |

The `/health/ready` endpoint returns 503 when any dependency is down. Connect it to an external uptime monitor (UptimeRobot, Betterstack, etc.).

---

## Monitoring

**Sentry** — set `SENTRY_DSN` in `.env`. The core-api automatically initializes Sentry on startup. This is the primary source for application errors and exceptions.

**`scripts/monitor.sh`** — covers what Sentry doesn't: container health, host disk usage, and Celery queue depth. Run it via cron and pipe failures into whatever alerting you already use (cron mail, healthchecks.io, a Slack webhook, etc.):
```bash
./scripts/monitor.sh yourdomain.com
```
```bash
# /etc/cron.d/tripclip-monitor
*/5 * * * * root cd /path/to/TripClip-AI && ./scripts/monitor.sh yourdomain.com >> /var/log/tripclip-monitor.log 2>&1
```
It exits non-zero on any problem (unhealthy container, disk >85%, `/health/ready` not 200).

**Container logs** — logs rotate automatically (50MB max, 10 files for core-api/celery-worker; 10MB/5 files for everything else):
```bash
docker compose -f docker-compose.prod.yml logs -f core-api
docker compose -f docker-compose.prod.yml logs -f celery-worker
```

**Celery queue** — check pending tasks:
```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD LLEN video_processing
```

---

## Database Backups

`scripts/backup.sh` dumps PostgreSQL (`pg_dump`) and MongoDB (`mongodump`) to timestamped, gzip-compressed files under `./backups/` (gitignored) and prunes anything older than `BACKUP_RETENTION_DAYS` (default 14).

```bash
./scripts/backup.sh                # backs up to ./backups/
BACKUP_RETENTION_DAYS=30 ./scripts/backup.sh /mnt/offsite-backups
```

Redis and Qdrant are intentionally excluded — Redis only holds the Celery broker queue and transient progress state (safe to lose), and Qdrant's travel-tip vectors are derived from Postgres data and can be rebuilt. If you need to retain raw uploaded videos, back up the `uploads_data` volume separately (find its full name with `docker volume ls | grep uploads_data` — it's prefixed with the Compose project name):
```bash
VOLUME=$(docker volume ls -q | grep uploads_data)
docker run --rm -v "$VOLUME":/data -v "$(pwd)/backups":/backup alpine \
    tar czf /backup/uploads-$(date +%Y%m%d).tar.gz -C /data .
```

Cron (daily at 2am):
```bash
# /etc/cron.d/tripclip-backup
0 2 * * * root cd /path/to/TripClip-AI && ./scripts/backup.sh >> /var/log/tripclip-backup.log 2>&1
```

**Restore** (destructive — asks for confirmation):
```bash
./scripts/restore.sh backups/postgres-20260101-020000.sql.gz backups/mongo-20260101-020000.archive.gz
```

Store backups off the production host (rsync to another machine, S3, etc.) — a backup that lives only on the server you're protecting against doesn't survive a disk failure.

---

## Deployment Verification (Smoke Test)

After every deploy or rollback, verify the stack from the outside — container `healthy` status is necessary but not sufficient (nginx routing, DNS, and TLS can still be wrong):

```bash
./scripts/smoke-test.sh yourdomain.com
```

Checks: HTTP→HTTPS redirect, web app loads, web-bff and mobile-bff health endpoints, both BFFs' routing reaches FastAPI (via a `422` on an intentionally empty login POST), and the TLS certificate is valid and readable. Exits non-zero if anything fails — safe to wire into CI/CD as a post-deploy gate.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes | Shared secret for JWT signing. Minimum 32 characters. |
| `GEMINI_API_KEY` | Yes | Google Gemini API key for video analysis. |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password. |
| `REDIS_PASSWORD` | Yes | Redis password. |
| `APP_ENV` | Yes | Set to `production` to enforce secret validation. |
| `NEXT_PUBLIC_API_URL` | Yes | Web BFF URL seen by the browser. Use `/api/web` with nginx. |
| `GEMINI_MODEL` | No | Gemini model name. Default: `gemini-2.5-flash`. |
| `WHISPER_MODEL` | No | Whisper model size. Default: `base`. |
| `USE_GEMINI` | No | Enable Gemini pipeline. Default: `true`. |
| `USE_GOOGLE_VISION` | No | Enable Google Vision API. Default: `false`. |
| `SENTRY_DSN` | No | Sentry DSN for error tracking. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Leave empty for defaults. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Only if `USE_GOOGLE_VISION=true` | Path inside the container to a GCP service account JSON file. Mount the file as a read-only volume; never COPY it into the image. |
| `OLLAMA_URL` | No | Base URL of an Ollama instance for travel-tips generation (e.g. `http://host.docker.internal:11434`). **Optional** — Ollama is not part of the Docker stack. Leave empty to disable the travel-tips stage; every other pipeline stage still runs. |
| `OLLAMA_MODEL` | No | Ollama model name to use for travel-tips generation. Default: `mistral`. Ignored if `OLLAMA_URL` is empty. |

### Travel tips (RAG) — optional dependency

`app/ml/rag_service.py` (`RAGService`) calls an external Ollama server over HTTP to generate travel tips. It is only used when **`USE_GEMINI=false`** (classic pipeline mode) — see `video_processor.py`'s stage 9. With the default `USE_GEMINI=true`, travel tips are generated by Gemini directly (`GeminiService.generate_travel_tips`) and Ollama is never called.

Ollama itself is **not** bundled with `docker-compose.yml` or `docker-compose.prod.yml` — if you run in classic mode and want travel tips, run Ollama yourself (locally, on a separate host, or as your own container) and point `OLLAMA_URL` at it.

If `OLLAMA_URL` is unset, `RAGService` initializes in a disabled state, logs a single info line, and `generate_travel_tips()` returns `{"tips": [], "summary": ""}` without making any network calls. No other pipeline stage is affected — this matches the existing `_safe_run()` degradation pattern used for every AI service in `video_processor.py`.

---

## Google Vision API Credentials (optional)

`USE_GOOGLE_VISION` defaults to `false`. If you enable it, inject credentials at runtime — never bake them into the Docker image.

**Correct approach:**
```bash
# Mount the key file as a read-only volume and set the env var
docker compose -f docker-compose.prod.yml run \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp.json \
  -v /path/to/your/key.json:/run/secrets/gcp.json:ro \
  celery-worker
```

Or in `docker-compose.prod.yml`, add to `celery-worker`:
```yaml
environment:
  GOOGLE_APPLICATION_CREDENTIALS: /run/secrets/gcp.json
volumes:
  - /path/to/your/key.json:/run/secrets/gcp.json:ro
```

**Never do this:**
```
# BAD — key ends up in every image layer
COPY credentials/ /app/credentials/
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/key.json
```

---

## Rollback

All images are built from source on deploy. `scripts/rollback.sh` wraps the procedure with a safety backup and a migration warning:

```bash
./scripts/rollback.sh          # rolls back to HEAD~1 (previous commit)
./scripts/rollback.sh <sha>    # rolls back to a specific commit
```

It will:
1. Show you current vs. target commit and ask for confirmation.
2. Run `scripts/backup.sh` first, so a bad rollback doesn't compound a bad deploy.
3. `git checkout` the target commit.
4. Warn about Alembic migrations — **schema migrations auto-apply on core-api startup but are never auto-reverted.** If the target commit predates a migration that already ran against this database, downgrade the schema manually before redeploying:
   ```bash
   docker compose -f docker-compose.prod.yml exec core-api alembic downgrade -1
   ```
   Compare `alembic history` between the two commits if unsure whether this applies.
5. Run `scripts/deploy.sh`.

Always finish with `./scripts/smoke-test.sh yourdomain.com` to confirm the rollback actually fixed things.
