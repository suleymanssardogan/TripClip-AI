# Deployment Guide

## Prerequisites

- Ubuntu 22.04+ server (minimum 4GB RAM, 40GB disk)
- Docker 24+ and Docker Compose plugin installed
- Domain name with A record pointing to the server IP
- Port 80 and 443 open in the firewall

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

Open `nginx/nginx.conf` and replace `CHANGEME.example.com` with your domain:
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

Let's Encrypt certificates expire every 90 days. Add a cron job:

```bash
# /etc/cron.d/tripclip-ssl
0 0 1 * * root cd /path/to/TripClip-AI && ./scripts/setup-ssl.sh yourdomain.com admin@yourdomain.com && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Health Checks

| Endpoint | Expected |
|----------|----------|
| `GET /health` | `{"status":"healthy"}` |
| `GET /health/ready` | `{"status":"ready","checks":{"postgres":"ok","redis":"ok"}}` |

The `/health/ready` endpoint returns 503 when any dependency is down. Connect it to an external uptime monitor (UptimeRobot, Betterstack, etc.).

---

## Monitoring

**Sentry** — set `SENTRY_DSN` in `.env`. The core-api automatically initializes Sentry on startup.

**Container logs** — logs rotate automatically (50MB max, 10 files for core-api):
```bash
docker compose -f docker-compose.prod.yml logs -f core-api
docker compose -f docker-compose.prod.yml logs -f celery-worker
```

**Celery queue** — check pending tasks:
```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD LLEN video_processing
```

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

All images are built from source on deploy. To roll back, check out the previous commit and redeploy:

```bash
git checkout HEAD~1
./scripts/deploy.sh
```
