"""
Global exception handler'lar — FastAPI app'e register edilir.

Tüm hatalar tek bir tutarlı JSON formatında döner:
{
    "error": {
        "code":    "VIDEO_NOT_FOUND",
        "message": "Video bulunamadı (ID: 42)",
        "details": {"video_id": 42}
    },
    "request_id": "abc123"   ← opsiyonel, middleware varsa
}
"""
import logging
import traceback
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import TripClipException

logger = logging.getLogger("tripclip.errors")


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict = None,
    request_id: str = None,
) -> JSONResponse:
    body = {
        "error": {
            "code":    code,
            "message": message,
            "details": details or {},
        }
    }
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


# ── 1. Uygulama kendi exception'ları ─────────────────────────────────────────

async def tripclip_exception_handler(request: Request, exc: TripClipException) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    logger.warning(
        "TripClipException | %s | %s | %s | %s",
        exc.code, exc.status_code, exc.message,
        f"details={exc.details}" if exc.details else "",
        extra={"request_id": rid, "path": request.url.path},
    )
    return _error_response(exc.status_code, exc.code, exc.message, exc.details, rid)


# ── 2. FastAPI/Starlette HTTPException ────────────────────────────────────────

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)

    # HTTP koduna göre makine-okunabilir code üret
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")

    if exc.status_code >= 500:
        logger.error(
            "HTTPException | %s | %s | path=%s",
            exc.status_code, exc.detail, request.url.path,
            extra={"request_id": rid},
        )
    else:
        logger.warning(
            "HTTPException | %s | %s | path=%s",
            exc.status_code, exc.detail, request.url.path,
            extra={"request_id": rid},
        )

    return _error_response(exc.status_code, code, str(exc.detail), request_id=rid)


# ── 3. Pydantic validation hataları ──────────────────────────────────────────

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)

    # Pydantic'in iç formatını düzleştir
    field_errors = []
    for err in exc.errors():
        loc  = " → ".join(str(l) for l in err["loc"] if l != "body")
        field_errors.append({"field": loc, "message": err["msg"], "type": err["type"]})

    logger.warning(
        "ValidationError | path=%s | errors=%s",
        request.url.path, field_errors,
        extra={"request_id": rid},
    )

    return _error_response(
        422,
        "VALIDATION_ERROR",
        "Gönderilen veriler geçersiz. Lütfen alanları kontrol edin.",
        details={"field_errors": field_errors},
        request_id=rid,
    )


# ── 4. Beklenmeyen hatalar (son çare) ─────────────────────────────────────────

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())[:8])
    logger.critical(
        "UNHANDLED EXCEPTION | path=%s | type=%s | %s\n%s",
        request.url.path,
        type(exc).__name__,
        str(exc),
        traceback.format_exc(),
        extra={"request_id": rid},
    )
    return _error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "Beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
        details={"request_id": rid},
        request_id=rid,
    )
