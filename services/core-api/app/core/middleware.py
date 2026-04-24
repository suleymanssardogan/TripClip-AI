"""
TripClip AI — HTTP Request/Response Logging Middleware.

Her isteğe benzersiz request_id atanır → log satırları izlenebilir hale gelir.
Yavaş istekler (> 2s) WARN seviyesinde loglanır.
"""
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("tripclip.access")

SLOW_REQUEST_THRESHOLD_S = 2.0

# Sağlık ve metric endpoint'leri loglamayı kirletmesin
_SKIP_PATHS = {"/health", "/", "/metrics", "/favicon.ico"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Her HTTP isteği için:
      - Benzersiz request_id oluşturur (request.state.request_id)
      - İstek başında → IN log
      - İstek sonunda → OUT log (süre + status code)
      - Yavaş istek → WARN seviyesinde ek log
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Sağlık endpoint'lerini atla
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.perf_counter()

        logger.info(
            "→ IN  | %s %s | ip=%s | rid=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            request_id,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "→ ERR | %s %s | %.3fs | rid=%s | %s: %s",
                request.method, request.url.path, elapsed,
                request_id, type(exc).__name__, exc,
            )
            raise

        elapsed = time.perf_counter() - start
        level   = logging.WARNING if elapsed > SLOW_REQUEST_THRESHOLD_S else logging.INFO

        logger.log(
            level,
            "← OUT | %s %s | %s | %.3fs%s | rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            " [SLOW]" if elapsed > SLOW_REQUEST_THRESHOLD_S else "",
            request_id,
        )

        # request_id'yi response header'a ekle → client-side debug kolaylaşır
        response.headers["X-Request-Id"] = request_id
        return response
