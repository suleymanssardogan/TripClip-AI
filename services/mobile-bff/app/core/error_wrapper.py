"""
Mobile BFF — Error Wrapper.

Core API'den gelen hataları yakalayıp iOS uygulamasına
kullanıcı dostu Türkçe mesajlar döndürür.

Kullanım:
    async with mobile_error_wrapper(request_id="abc"):
        resp = await client.get(...)
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger("mobile-bff.errors")

# Core API error code → iOS kullanıcı mesajı
_MOBILE_MESSAGES: dict[str, str] = {
    "VIDEO_NOT_FOUND":           "Bu video artık mevcut değil.",
    "VIDEO_PROCESSING_FAILED":   "Video işlenirken bir sorun oluştu. Lütfen tekrar deneyin.",
    "INVALID_FILE_TYPE":         "Yalnızca video dosyaları yüklenebilir.",
    "FILE_TOO_LARGE":            "Video dosyası çok büyük. 100 MB altında bir video seçin.",
    "DUPLICATE_EMAIL":           "Bu e-posta adresi zaten kayıtlı.",
    "DUPLICATE_USERNAME":        "Bu kullanıcı adı alınmış. Farklı bir isim deneyin.",
    "AUTH_ERROR":                "E-posta veya şifre hatalı.",
    "UNAUTHORIZED":              "Oturumunuz sona erdi. Lütfen tekrar giriş yapın.",
    "PERMISSION_DENIED":         "Bu işleme erişim izniniz yok.",
    "RATE_LIMIT_EXCEEDED":       "Çok fazla istek gönderdiniz. Biraz bekleyin.",
    "VALIDATION_ERROR":          "Gönderilen bilgiler eksik veya hatalı.",
    "ML_SERVICE_UNAVAILABLE":    "AI analiz servisi şu an meşgul. Lütfen bekleyin.",
    "DATABASE_ERROR":            "Sunucu geçici olarak kullanılamıyor.",
    "SERVICE_UNAVAILABLE":       "Servis şu an kullanılamıyor. Lütfen daha sonra deneyin.",
    "INTERNAL_SERVER_ERROR":     "Beklenmeyen bir hata oluştu.",
}

_DEFAULT_MESSAGE = "Bir şeyler ters gitti. Lütfen tekrar deneyin."


def _parse_core_error(data: dict) -> tuple[str, str, int]:
    """
    Core API hata yanıtını çözümle.
    (code, user_message, status_code) döner.
    """
    err      = data.get("error", {})
    code     = err.get("code", "INTERNAL_SERVER_ERROR")
    message  = _MOBILE_MESSAGES.get(code, _DEFAULT_MESSAGE)
    status   = 500 if code in {"INTERNAL_SERVER_ERROR", "DATABASE_ERROR", "ML_SERVICE_UNAVAILABLE"} else 400
    if code in {"UNAUTHORIZED", "AUTH_ERROR"}:
        status = 401
    if code in {"VIDEO_NOT_FOUND"}:
        status = 404
    if code == "RATE_LIMIT_EXCEEDED":
        status = 429
    return code, message, status


@asynccontextmanager
async def mobile_error_wrapper(request_id: Optional[str] = None):
    """
    Context manager — httpx ve Core API hatalarını iOS formatına çevirir.

    async with mobile_error_wrapper(request_id=rid):
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise_from_response(resp)
    """
    try:
        yield
    except HTTPException:
        raise  # Zaten işlenmiş, tekrar fırlatma
    except httpx.ConnectError:
        logger.error("Core API'ye bağlanılamadı | rid=%s", request_id)
        raise HTTPException(
            503,
            detail={
                "code":    "SERVICE_UNAVAILABLE",
                "message": "Sunucuya ulaşılamıyor. İnternet bağlantınızı kontrol edin.",
            },
        )
    except httpx.TimeoutException:
        logger.warning("Core API timeout | rid=%s", request_id)
        raise HTTPException(
            504,
            detail={
                "code":    "GATEWAY_TIMEOUT",
                "message": "İstek zaman aşımına uğradı. Lütfen tekrar deneyin.",
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
    """
    Core API'den >= 400 gelen yanıtı iOS dostu HTTPException'a çevirir.
    mobile_error_wrapper context'i içinde çağrılır.
    """
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
