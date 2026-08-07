# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TripClip AI — AI-powered travel video analyzer that extracts locations from Instagram Reels and generates optimized travel itineraries. Academic project (Fırat University, 2026).

## Running the Stack

**Full stack (recommended):**
```bash
cp .env.example .env  # then add GEMINI_API_KEY
docker-compose up -d
```

**Infrastructure only (for local service development):**
```bash
docker-compose up -d postgres redis mongodb qdrant
```

**Individual services (local dev with hot-reload):**
```bash
# Core API (port 8000)
cd services/core-api && uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal, same dir)
cd services/core-api && celery -A app.core.celery_app worker --loglevel=info -Q video_processing --pool=solo

# Web BFF (port 8002)
cd services/web-bff && uvicorn app.main:app --reload --port 8002

# Mobile BFF (port 8001)
cd services/mobile-bff && uvicorn app.main:app --reload --port 8001

# Next.js web frontend (port 3000)
cd web && npm run dev
```

**Tests:**
```bash
cd services/core-api && pytest
cd services/core-api && pytest tests/path/to/test_file.py::test_name  # single test
```

**Database migrations:**
```bash
cd services/core-api && alembic upgrade head
# Migrations also auto-apply on core-api startup via lifespan hook
```

**Web:**
```bash
cd web && npm run lint
cd web && npm run build
```

## Architecture

### Services

| Service | Port | Role |
|---------|------|------|
| `core-api` | 8000 | ML pipeline, business logic, DB access |
| `web-bff` | 8002 | Proxy/transformer for the Next.js web app |
| `mobile-bff` | 8001 | Proxy/transformer for iOS app |
| `celery-worker` | — | Async video processing (same image as core-api) |

BFFs talk to core-api over Docker internal networking. Frontends never call core-api directly.

### Databases

- **PostgreSQL** — users, videos (metadata + AI results), plans
- **Redis db=0** — Celery broker; **db=2** — Celery results; also stores per-video progress via `set_progress(video_id, stage, percent)`
- **MongoDB** — secondary storage
- **Qdrant** — vector DB for RAG travel tips (sentence-transformers embeddings)

### Video Processing Pipeline

Upload triggers `process_video_task` (or `process_url_task` for Instagram URLs via yt-dlp) on the `video_processing` Celery queue. The task delegates to `VideoProcessingService` (`services/core-api/app/core/services/video_processor.py`), which runs all AI stages in parallel using `ThreadPoolExecutor`.

Each AI stage is wrapped in `_safe_run()` — if a service fails, it logs a fallback and the pipeline continues. A degradation report is logged after every video.

**Pipeline stages (env flags control which run):**
1. Frame extraction (FFmpeg/OpenCV)
2. Computer vision: YOLO object detection + optional Google Vision API
3. OCR: RapidOCR
4. Speech-to-text: Whisper
5. NER: Turkish BERT (HuggingFace transformers)
6. **Gemini** (`USE_GEMINI=true`): replaces steps 2–5 with a single multimodal call via REST (no SDK)
7. Location geocoding: Nominatim
8. Location deduplication: Haversine distance
9. Route optimization: TSP solver
10. RAG travel tips: Qdrant + sentence-transformers

### Core-API Layer Structure

```
app/
  api/internal/       ← FastAPI routes (HTTP boundary)
  application/
    services/         ← Use cases (auth_service, video_service)
    dto/              ← Pydantic request/response schemas
  domain/repositories/  ← Repository interfaces
  infrastructure/repositories/  ← SQLAlchemy implementations
  models/             ← SQLAlchemy ORM models
  ml/                 ← AI service modules (one file per service)
  core/
    services/video_processor.py  ← Pipeline orchestrator
    celery_app.py     ← Celery configuration
    database.py       ← SQLAlchemy session factory
    redis.py          ← Redis client + set_progress()
  tasks/video_tasks.py  ← Celery task definitions
```

### Web Frontend (Next.js 16 / React 19)

`web/src/lib/api.ts` is the single API client — all requests go to Web BFF at `http://127.0.0.1:8002/api/web`. JWT token stored in `localStorage`. Error responses follow `{ error: { code, message } }` envelope (BFF format) or legacy `{ detail: "..." }` (FastAPI format).

Pages: `/` landing, `/login`, `/signup`, `/dashboard`, `/explore`, `/analyze/[id]`, `/editor/[id]`, `/share/[id]`

> **Note:** `web/AGENTS.md` warns that Next.js 16 has breaking API changes from prior versions — read `node_modules/next/dist/docs/` before writing Next.js-specific code.

### iOS (Swift)

- `TripClipShare/ShareViewController.swift` — Share Extension: detects Instagram URL → background uploads to Mobile BFF via `BackgroundUploader`
- `TripClipApp/ProcessingView.swift` + `ProcessingViewModel.swift` — polls Mobile BFF for video processing progress

### Error Response Format

All services return errors as:
```json
{ "error": { "code": "ERROR_CODE", "message": "User-facing message" } }
```
Core-API uses `TripClipException` → `tripclip_exception_handler` for structured errors.

## Key Environment Variables

| Variable | Where used | Notes |
|----------|-----------|-------|
| `GEMINI_API_KEY` | core-api, celery-worker | Required for Gemini mode |
| `GEMINI_MODEL` | celery-worker | Default: `gemini-2.5-flash` |
| `USE_GEMINI` | celery-worker | `true` enables Gemini instead of traditional ML |
| `USE_HYBRID` | celery-worker | `true` enables hybrid mode |
| `WHISPER_MODEL` | celery-worker | Default: `base` |
| `USE_GOOGLE_VISION` | celery-worker | Default: `false` |
| `SENTRY_DSN` | core-api | Optional; Sentry only activates when set |
| `YT_DLP_COOKIES` | celery-worker | Path to cookies.txt for private Instagram Reels |
| `APNS_KEY_ID` / `APNS_TEAM_ID` / `APNS_BUNDLE_ID` / `APNS_AUTH_KEY` | celery-worker | Optional; push (processing complete/failed) only activates when all four are set |
| `APNS_USE_SANDBOX` | celery-worker | `true` for TestFlight/dev builds, `false` for App Store. Default: `true` |

All vars in `docker-compose.yml`. Copy `.env.example` → `.env` and set `GEMINI_API_KEY`.
