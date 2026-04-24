"""
TripClip AI — Özel exception hiyerarşisi.

Kullanım:
    raise VideoNotFoundException(video_id=42)
    raise AuthException("E-posta zaten kayıtlı")

Tüm bu exception'lar global handler tarafından yakalanır
ve tutarlı JSON formatında döndürülür.
"""
from typing import Optional, Any, Dict


class TripClipException(Exception):
    """Tüm uygulama hatalarının temel sınıfı."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message     = message
        self.code        = code          # makine-okunabilir hata kodu
        self.status_code = status_code
        self.details     = details or {}


# ── Auth ──────────────────────────────────────────────────────────────────────

class AuthException(TripClipException):
    """Kimlik doğrulama / yetkilendirme hataları."""
    def __init__(self, message: str = "Kimlik doğrulama başarısız", code: str = "AUTH_ERROR"):
        super().__init__(message, code=code, status_code=401)


class PermissionDeniedException(TripClipException):
    def __init__(self, message: str = "Bu işlem için yetkiniz yok"):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403)


class DuplicateEmailException(TripClipException):
    def __init__(self, email: str):
        super().__init__(
            f"'{email}' adresi zaten kayıtlı",
            code="DUPLICATE_EMAIL",
            status_code=400,
            details={"email": email},
        )


class DuplicateUsernameException(TripClipException):
    def __init__(self, username: str):
        super().__init__(
            f"'{username}' kullanıcı adı zaten alınmış",
            code="DUPLICATE_USERNAME",
            status_code=400,
            details={"username": username},
        )


# ── Video ─────────────────────────────────────────────────────────────────────

class VideoNotFoundException(TripClipException):
    def __init__(self, video_id: int):
        super().__init__(
            f"Video bulunamadı (ID: {video_id})",
            code="VIDEO_NOT_FOUND",
            status_code=404,
            details={"video_id": video_id},
        )


class VideoProcessingException(TripClipException):
    def __init__(self, video_id: int, reason: str):
        super().__init__(
            f"Video işleme hatası: {reason}",
            code="VIDEO_PROCESSING_FAILED",
            status_code=500,
            details={"video_id": video_id, "reason": reason},
        )


class InvalidFileTypeException(TripClipException):
    def __init__(self, content_type: str):
        super().__init__(
            f"Desteklenmeyen dosya türü: {content_type}. Yalnızca video dosyaları kabul edilir.",
            code="INVALID_FILE_TYPE",
            status_code=400,
            details={"received": content_type},
        )


class FileTooLargeException(TripClipException):
    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(
            f"Dosya çok büyük ({size_mb:.1f} MB). Maksimum: {max_mb} MB",
            code="FILE_TOO_LARGE",
            status_code=400,
            details={"size_mb": size_mb, "max_mb": max_mb},
        )


# ── Database ──────────────────────────────────────────────────────────────────

class DatabaseException(TripClipException):
    def __init__(self, operation: str, reason: str = ""):
        super().__init__(
            f"Veritabanı hatası: {operation}" + (f" — {reason}" if reason else ""),
            code="DATABASE_ERROR",
            status_code=503,
            details={"operation": operation},
        )


# ── ML / Servis ───────────────────────────────────────────────────────────────

class MLServiceUnavailableException(TripClipException):
    def __init__(self, service: str):
        super().__init__(
            f"AI servisi şu an kullanılamıyor: {service}",
            code="ML_SERVICE_UNAVAILABLE",
            status_code=503,
            details={"service": service},
        )
