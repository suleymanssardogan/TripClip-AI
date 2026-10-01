from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
from app.routes import auth, plans, analytics, trip_sharing, trip_optimization, trips, trip_assistant
from app.core.auth import ACCESS_COOKIE, REFRESH_COOKIE
from app.routes import videos as videos_router
import logging
import sys
import time
import uuid
import os

# Sentry — yalnızca DSN tanımlanmışsa etkinleştir (core-api ile aynı desen)
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn and "sentry" in {v.strip().lower() for v in os.getenv("PRIVACY_REVIEWED_PROVIDERS", "").split(",")}:
    import sentry_sdk
    from app.core.privacy import scrub_error_event
    sentry_sdk.init(
        dsn=_sentry_dsn,
        send_default_pii=False,
        include_local_variables=False,
        before_send=scrub_error_event,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.0")),
    )

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
_access_log = logging.getLogger("web-bff.access")

_SKIP_PATHS = {"/health", "/", "/metrics", "/favicon.ico"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)
        rid = str(uuid.uuid4())[:8]
        request.state.request_id = rid
        start = time.perf_counter()
        _access_log.info("→ IN  | %s %s | rid=%s", request.method, request.url.path, rid)
        try:
            response = await call_next(request)
        except Exception as exc:
            _access_log.error("→ ERR | %s %s | rid=%s | %s", request.method, request.url.path, rid, exc)
            raise
        elapsed = time.perf_counter() - start
        lvl = logging.WARNING if elapsed > 2.0 else logging.INFO
        _access_log.log(lvl, "← OUT | %s %s | %s | %.3fs%s | rid=%s",
            request.method, request.url.path, response.status_code, elapsed,
            " [SLOW]" if elapsed > 2.0 else "", rid)
        response.headers["X-Request-Id"] = rid
        return response


class CookieOriginMiddleware(BaseHTTPMiddleware):
    """Cookie-authenticated writes must originate from this site."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if (request.url.path.startswith("/api/web/")
                and request.method not in {"GET", "HEAD", "OPTIONS"}
                and (ACCESS_COOKIE in request.cookies or REFRESH_COOKIE in request.cookies)):
            host = request.headers.get("host", "")
            scheme = "https" if os.getenv("APP_ENV") == "production" else request.url.scheme
            expected_origin = f"{scheme}://{host}"
            allowed_origins = {expected_origin, *ALLOWED_ORIGINS}
            if request.headers.get("origin") not in allowed_origins:
                return JSONResponse(status_code=403, content={"code": "INVALID_ORIGIN", "message": "Geçersiz istek kaynağı."})
        return await call_next(request)

# Web BFF: yalnızca Next.js web uygulamasından istek gelir.
# ALLOWED_ORIGINS env ile production domain eklenebilir.
_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else ([] if os.getenv("APP_ENV") == "production" else [
        "http://localhost:3000",    # local Next.js dev
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ])
)

app = FastAPI(
    title="TripClip AI - Web BFF",
    description="Backend for Frontend - Web",
    version="1.0.0"
)

# Rate limiter — /auth/refresh, /auth/logout gibi yeni endpoint'ler için
# (core-api/mobile-bff ile aynı kurulum).
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Host-header doğrulaması. nginx gerçek public domain'i Host header'ı olarak
# iletir (bkz. nginx/nginx.conf `proxy_set_header Host $host`), bu yüzden
# varsayılan "*" (kısıtlama yok) — production'da ALLOWED_HOSTS ile kendi
# domain'inize daraltın (örn. "tripclip.app,www.tripclip.app").
_raw_hosts = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()] or ["*"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CookieOriginMiddleware)

# ── Prometheus metrikleri ──────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, include_in_schema=False)

# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "Lütfen formdaki hataları düzeltin.", "detail": exc.errors()},
    )

@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={"code": "HTTP_ERROR", "message": str(detail)})

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logging.getLogger("web-bff").error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_SERVER_ERROR", "message": "Beklenmeyen bir hata oluştu."},
    )

app.include_router(auth.router,          prefix="/api/web")
app.include_router(plans.router,         prefix="/api/web")
app.include_router(videos_router.router, prefix="/api/web")
app.include_router(analytics.router,     prefix="/api/web")
app.include_router(trip_sharing.router,  prefix="/api/web")
app.include_router(trip_optimization.router, prefix="/api/web")
app.include_router(trips.router,         prefix="/api/web")
app.include_router(trip_assistant.router, prefix="/api/web")


@app.get("/")
async def root():
    return {"service": "Web BFF", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web-bff"}
