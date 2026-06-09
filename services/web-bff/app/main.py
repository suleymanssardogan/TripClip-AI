from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.routes import auth, plans
from app.routes import videos as videos_router
import logging
import sys
import time
import uuid
import os

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

# Web BFF: yalnızca Next.js web uygulamasından istek gelir.
# ALLOWED_ORIGINS env ile production domain eklenebilir.
_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else [
        "http://localhost:3000",    # local Next.js dev
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
)

app = FastAPI(
    title="TripClip AI - Web BFF",
    description="Backend for Frontend - Web",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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


@app.get("/")
async def root():
    return {"service": "Web BFF", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web-bff"}
