from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.routes import videos, auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import sys
import time
import uuid
import os as _os

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
_access_log = logging.getLogger("mobile-bff.access")

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


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="TripClip AI - Mobile BFF",
    description="Backend for Frontend - iOS",
    version="0.1.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mobile BFF: iOS native app CORS göndermez.
_raw = _os.getenv("ALLOWED_ORIGINS", "")
_MOBILE_ORIGINS = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else [
        "http://localhost:3001",    # Next.js (Swagger erişimi için)
        "http://127.0.0.1:3001",
        "http://localhost:8000",    # core-api Swagger UI
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_MOBILE_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(RequestLoggingMiddleware)


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "Geçersiz istek formatı.", "detail": exc.errors()},
    )

@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={"code": "HTTP_ERROR", "message": str(detail)})

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logging.getLogger("mobile-bff").error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_SERVER_ERROR", "message": "Beklenmeyen bir hata oluştu."},
    )


app.include_router(auth.router, prefix="/api/mobile")
app.include_router(videos.router, prefix="/api/mobile")


@app.get("/")
async def root():
    return {
        "service": "Mobile BFF",
        "platform": "iOS",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mobile-bff"}
