from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import sys
import os

from app.core.exceptions import TripClipException
from app.core.error_handlers import (
    tripclip_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.core.middleware import RequestLoggingMiddleware

# Sentry — yalnızca DSN tanımlanmışsa etkinleştir (prod ortamında .env ile verilir)
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "1.0")),
        profile_session_sample_rate=1.0,
        profile_lifecycle="trace",
    )

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # ← Docker log'a yaz!
    ]
)

_startup_logger = logging.getLogger("alembic.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: Alembic migration'larını otomatik uygula."""
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_cmd
        from pathlib import Path

        alembic_cfg = AlembicConfig(str(Path(__file__).parent.parent / "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location",
            str(Path(__file__).parent.parent / "alembic")
        )
        alembic_cmd.upgrade(alembic_cfg, "head")
        _startup_logger.info("✅ Alembic migration tamamlandı")
    except Exception as e:
        _startup_logger.warning(f"⚠️ Alembic migration atlandı: {e}")

    yield  # ← uygulama burada çalışır


# Rate limiter — IP başına istek limiti
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="TripClip AI - Core API",
    description="Business logic and AI services",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global exception handlers ─────────────────────────────────────────────────
app.add_exception_handler(TripClipException, tripclip_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Core API sadece BFF'lerden (iç Docker ağı) çağrılır — browser erişimi yok.
# ALLOWED_ORIGINS env ile production'da daraltılabilir.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else [
        "http://localhost:8001",   # mobile-bff (iç ağ)
        "http://localhost:8002",   # web-bff (iç ağ)
        "http://mobile-bff:8001",
        "http://web-bff:8002",
        "http://localhost:3001",   # local geliştirme (Swagger UI vb.)
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)

# ── Request logging middleware ────────────────────────────────────────────────
# CORSMiddleware'den SONRA eklenir → her isteğe request_id atanır
app.add_middleware(RequestLoggingMiddleware)


@app.get("/")
async def root():
    return {"service": "Core API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "core-api"}


@app.get("/health/ready")
async def health_ready():
    """
    Readiness check — verifies all critical dependencies.
    Returns 200 when the service can handle requests, 503 when degraded.
    Used by nginx upstream health checks and monitoring.
    """
    from fastapi.responses import JSONResponse
    from sqlalchemy import text as sa_text
    from app.core.database import SessionLocal

    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {type(exc).__name__}"

    # Redis
    try:
        from app.core.redis import get_redis
        r = get_redis()
        if r:
            r.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "unavailable"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ready" if all_ok else "degraded",
            "service": "core-api",
            "checks": checks,
        },
    )


# Import routers AFTER app creation
from app.api.internal import videos, auth
app.include_router(videos.router)
app.include_router(auth.router)
