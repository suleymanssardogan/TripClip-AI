"""
Web BFF — Error Wrapper.

Core API'den gelen hataları yakalayıp Next.js ön yüzüne
kullanıcı dostu mesajlar döndürür.
Web mesajları mobil mesajlardan daha uzun ve açıklayıcı olabilir.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger("web-bff.errors")

# Core API error code → web kullanıcı mesajı
_WEB_MESSAGES: dict[str, str] = {
    "VIDEO_NOT_FOUND":           "Aradığınız gezi planı bulunamadı. Silinmiş veya gizlenmiş olabilir.",
    "VIDEO_PROCESSING_FAILED":   "Video analizi sırasında bir hata oluştu. Farklı bir video deneyebilirsiniz.",
    "INVALID_FILE_TYPE":         "Yalnızca video dosyaları yüklenebilir (MP4, MOV, AVI).",
    "FILE_TOO_LARGE":            "Dosya boyutu çok büyük. Lütfen 200 MB'tan küçük bir video seçin.",
    "DUPLICATE_EMAIL":           "Bu e-posta adresiyle zaten bir hesap mevcut. Giriş yapmayı deneyin.",
    "DUPLICATE_USERNAME":        "Bu kullanıcı adı başkası tarafından kullanılıyor.",
    "AUTH_ERROR":                "E-posta adresi veya şifre hatalı. Lütfen bilgilerinizi kontrol edin.",
    "UNAUTHORIZED":              "Bu sayfayı görüntülemek için giriş yapmalısınız.",
    "PERMISSION_DENIED":         "Bu içeriğe erişim izniniz bulunmuyor.",
    "RATE_LIMIT_EXCEEDED":       "Çok fazla istek gönderildi. Lütfen bir süre bekleyip tekrar deneyin.",
    "VALIDATION_ERROR":          "Lütfen formdaki hataları düzeltin ve tekrar gönderin.",
    "ML_SERVICE_UNAVAILABLE":    "Yapay zeka analiz servisi geçici olarak meşgul. Birkaç dakika sonra tekrar deneyin.",
    "DATABASE_ERROR":            "Sunucu veritabanına ulaşamıyor. Ekibimiz bilgilendirildi.",
    "SERVICE_UNAVAILABLE":       "Servis geçici olarak kullanılamıyor. Lütfen daha sonra tekrar ziyaret edin.",
    "INTERNAL_SERVER_ERROR":     "Beklenmeyen bir sunucu hatası oluştu. Sorun devam ederse destek ekibiyle iletişime geçin.",
}

_DEFAULT_MESSAGE = "Bir hata oluştu. Lütfen sayfayı yenileyip tekrar deneyin."


def _parse_core_error(data: dict) -> tuple[str, str, int]:
    err     = data.get("error", {})
    code    = err.get("code", "INTERNAL_SERVER_ERROR")
    message = _WEB_MESSAGES.get(code, _DEFAULT_MESSAGE)

    if code in {"UNAUTHORIZED", "AUTH_ERROR"}:
        status = 401
    elif code == "PERMISSION_DENIED":
        status = 403
    elif code == "VIDEO_NOT_FOUND":
        status = 404
    elif code == "RATE_LIMIT_EXCEEDED":
        status = 429
    elif code in {"DATABASE_ERROR", "ML_SERVICE_UNAVAILABLE", "SERVICE_UNAVAILABLE", "INTERNAL_SERVER_ERROR"}:
        status = 503
    else:
        status = 400

    return code, message, status


@asynccontextmanager
async def web_error_wrapper(request_id: Optional[str] = None):
    """
    Context manager — httpx ve Core API hatalarını web formatına çevirir.

    async with web_error_wrapper(request_id=rid):
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise_from_response(resp)
    """
    try:
        yield
    except HTTPException:
        raise
    except httpx.ConnectError:
        logger.error("Core API'ye bağlanılamadı | rid=%s", request_id)
        raise HTTPException(
            503,
            detail={
                "code":    "SERVICE_UNAVAILABLE",
                "message": "Sunucuya ulaşılamıyor. Lütfen internet bağlantınızı kontrol edin.",
            },
        )
    except httpx.TimeoutException:
        logger.warning("Core API zaman aşımı | rid=%s", request_id)
        raise HTTPException(
            504,
            detail={
                "code":    "GATEWAY_TIMEOUT",
                "message": "Sunucu yanıt vermedi. Lütfen sayfayı yenileyin.",
            },
        )
    except httpx.HTTPStatusError as exc:
        _handle_status_error(exc, request_id)
    except Exception as exc:
        logger.error("Beklenmeyen BFF hatası | rid=%s | %s", request_id, exc, exc_info=True)
        raise HTTPException(
            500,
            detail={
                "code":    "INTERNAL_SERVER_ERROR",
                "message": _DEFAULT_MESSAGE,
            },
        )


def raise_from_response(resp: httpx.Response, request_id: Optional[str] = None) -> None:
    try:
        data = resp.json()
    except Exception:
        data = {}

    code, message, status = _parse_core_error(data)
    logger.warning(
        "Core API error | status=%s | code=%s | rid=%s",
        resp.status_code, code, request_id,
    )
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def _handle_status_error(exc: httpx.HTTPStatusError, request_id: Optional[str]) -> None:
    try:
        data = exc.response.json()
    except Exception:
        data = {}
    code, message, status = _parse_core_error(data)
    logger.error(
        "httpx HTTPStatusError | status=%s | code=%s | rid=%s",
        exc.response.status_code, code, request_id,
    )
    raise HTTPException(status_code=status, detail={"code": code, "message": message})
