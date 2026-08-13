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
    "DAILY_QUOTA_EXCEEDED":      "Günlük video işleme limitine ulaştınız. Lütfen yarın tekrar deneyin.",
    "VALIDATION_ERROR":          "Gönderilen bilgiler eksik veya hatalı.",
    "INVALID_STOP_ORDER":        "Durak sırası güncellenemedi. Sayfayı yenileyip tekrar deneyin.",
    "TRIP_NOT_FOUND":            "Bu gezi artık mevcut değil.",
    "INVALID_TRIP_PLACES":       "Seçilen mekanlardan gezi oluşturulamadı.",
    "INVALID_TRIP_STOP_ORDER":   "Durak sırası güncellenemedi. Sayfayı yenileyip tekrar deneyin.",
    "INVALID_SHARE_REQUEST":    "Davet oluşturulamadı. Bilgileri kontrol edip tekrar deneyin.",
    "SHARE_NOT_FOUND":          "Bu davet artık mevcut değil.",
    "SHARE_TOKEN_INVALID":      "Bu davet linki artık geçerli değil.",
    "CANNOT_JOIN_OWN_TRIP":     "Kendi gezinize collaborator olarak katılamazsınız.",
    "INVALID_OPTIMIZATION_REQUEST": "Gezi optimize edilemedi. Seçimlerinizi kontrol edip tekrar deneyin.",
    "ITINERARY_NOT_FOUND":      "Bu itinerary artık mevcut değil.",
    "APPLY_HISTORY_NOT_FOUND":  "Bu uygulama geçmişi kaydı artık mevcut değil.",
    "STALE_UNDO":               "Yalnızca en son uygulama geri alınabilir. Bu kayıt artık en son değil.",
    "ML_SERVICE_UNAVAILABLE":    "AI analiz servisi şu an meşgul. Lütfen bekleyin.",
    "DATABASE_ERROR":            "Sunucu geçici olarak kullanılamıyor.",
    "SERVICE_UNAVAILABLE":       "Servis şu an kullanılamıyor. Lütfen daha sonra deneyin.",
    "INTERNAL_SERVER_ERROR":     "Beklenmeyen bir hata oluştu.",
    "INVALID_ASSISTANT_REQUEST": "Lütfen asistana bir soru yazın.",
    "ASSISTANT_UNAVAILABLE":     "AI asistanı şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
    # M34 — refresh-token kodları ÖNCEDEN burada YOKTU, bu yüzden hepsi
    # aşağıdaki varsayılan 400'e düşüyordu — core-api'nin AslI 401'i
    # kayboluyordu (bkz. _parse_core_error, ve Milestone 26'nın "unregistered
    # error codes silently degrade" uyarısı — burada REFRESH_TOKEN ailesi
    # için AYNI hata tekrar bulundu ve düzeltildi). iOS `apiError.isUnauthorized`
    # kontrolü YALNIZCA gerçek 401'de doğru tetiklenir (bkz.
    # AuthEnvironment.refreshTokens/handleUnauthorized) — 400 dönerse çalıntı/
    # yeniden kullanılmış bir refresh token client'ı ZORLA çıkış YAPTIRMAZDI.
    "REFRESH_TOKEN_INVALID":     "Oturumunuz geçersiz. Lütfen tekrar giriş yapın.",
    "REFRESH_TOKEN_EXPIRED":     "Oturumunuzun süresi doldu. Lütfen tekrar giriş yapın.",
    "REFRESH_TOKEN_REUSED":      "Güvenlik nedeniyle oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.",
    "REFRESH_TOKEN_RACE_LOST":   "Oturum yenilenemedi. Lütfen tekrar deneyin.",
    "PASSWORD_RESET_TOKEN_INVALID": "Bu şifre sıfırlama linki geçersiz.",
    "PASSWORD_RESET_TOKEN_EXPIRED": "Bu şifre sıfırlama linkinin süresi doldu. Yeni bir istek gönderin.",
    "PASSWORD_RESET_TOKEN_USED":    "Bu şifre sıfırlama linki zaten kullanılmış.",
    "GOOGLE_AUTH_UNAVAILABLE":      "Google ile giriş şu anda kullanılamıyor.",
    "GOOGLE_EMAIL_NOT_VERIFIED":    "Bu e-posta adresiyle zaten bir hesap var. Lütfen normal giriş yapın.",
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
    # M38 — `SERVICE_UNAVAILABLE` burada hiç kayıtlı değildi (yalnızca bu
    # dosyanın KENDİ ürettiği 503'ler, ör. ConnectError yakalayan
    # `mobile_error_wrapper`, bu koddan bağımsız olarak zaten 503 dönüyordu)
    # — ama core-api'nin YANITININ KENDİSİ bu kodu taşırsa (bkz. mesaj
    # sözlüğündeki mevcut "SERVICE_UNAVAILABLE" girdisi — beklenen bir kod)
    # varsayılan 400'e düşüyordu. web-bff bu kodu zaten 503'e eşliyor
    # (cross-platform contract asimetrisi, M38 audit bulgusu).
    status   = 500 if code in {"INTERNAL_SERVER_ERROR", "DATABASE_ERROR", "ML_SERVICE_UNAVAILABLE", "ASSISTANT_UNAVAILABLE", "SERVICE_UNAVAILABLE"} else 400
    # M34 — REFRESH_TOKEN_* kodları burada hiç kayıtlı değildi ve varsayılan
    # 400'e düşüyordu (core-api hepsini 401 döndürüyor). Bu, çalıntı/yeniden
    # kullanılmış bir refresh token'ın iOS'ta `apiError.isUnauthorized`
    # tetiklemesini engelliyordu → client zorla çıkış YAPMIYORDU.
    if code in {
        "UNAUTHORIZED", "AUTH_ERROR",
        "REFRESH_TOKEN_INVALID", "REFRESH_TOKEN_EXPIRED", "REFRESH_TOKEN_REUSED", "REFRESH_TOKEN_RACE_LOST",
        "PASSWORD_RESET_TOKEN_INVALID", "PASSWORD_RESET_TOKEN_EXPIRED", "PASSWORD_RESET_TOKEN_USED",
        "GOOGLE_AUTH_UNAVAILABLE", "GOOGLE_EMAIL_NOT_VERIFIED",
    }:
        status = 401
    if code in {"VIDEO_NOT_FOUND", "TRIP_NOT_FOUND", "SHARE_NOT_FOUND", "SHARE_TOKEN_INVALID", "ITINERARY_NOT_FOUND", "APPLY_HISTORY_NOT_FOUND"}:
        status = 404
    # Yetki hatası 400'e düşüyordu; başkasının planını silmeye/düzenlemeye
    # çalışmak istemcide "geçersiz istek" gibi görünüyordu.
    if code in {"PERMISSION_DENIED", "FORBIDDEN"}:
        status = 403
    if code in {"RATE_LIMIT_EXCEEDED", "DAILY_QUOTA_EXCEEDED"}:
        status = 429
    # Bir apply-history kaydının artık en son olmadığı anlamına gelir —
    # yeniden denemek anlamsız (istek KENDİSİ geçersiz değil, DURUM
    # değişmiş) — bu yüzden 400 DEĞİL, 409 (Apply History & Undo milestone'u).
    if code == "STALE_UNDO":
        status = 409
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
