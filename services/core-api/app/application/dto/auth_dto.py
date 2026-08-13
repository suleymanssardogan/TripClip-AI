"""
Auth DTO'ları — API request/response şemaları.
Route handler'lar sadece bu modelleri görür; DB modelleri görünmez.
"""
from pydantic import BaseModel, field_validator
from typing import Optional


def _validate_password_strength(v: str) -> str:
    """Kayıt VE şifre sıfırlama arasında PAYLAŞILAN tek kural — bkz. M34
    milestone'unun kendi "password validation must reuse the existing
    password rules" gereksinimi. Yalnızca yeni şifre belirlenirken
    uygulanır (login'de DEĞİL) — mevcut kullanıcıların eski şifreleriyle
    giriş yapamaz hale gelmemesi için."""
    if len(v) < 8:
        raise ValueError("Şifre en az 8 karakter olmalıdır.")
    return v


# ── Request DTO'ları ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str       # EmailStr yerine str — test/prod tüm domain'lerde çalışır
    password: str
    username: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    email: str
    password: str


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: Optional[str] = None


class GoogleSignInRequest(BaseModel):
    # Yetkilendirme kodu — istemcinin (Web/iOS) Google'ın KENDİ yetkilendirme
    # ekranından aldığı, TEK KULLANIMLIK kod. Client secret hiçbir zaman
    # istemciye gönderilmez (bkz. milestone Req "do not expose client
    # secrets to Web/iOS clients") — değişim SADECE core-api'de olur.
    code: str
    # İstemcinin yetkilendirme URL'sini kurarken KULLANDIĞI redirect_uri —
    # Google'ın token değişimi, bu değerin yetkilendirme isteğindekiyle
    # AYNI olmasını ZORUNLU kılar. core-api ayrıca bunu kendi
    # GOOGLE_ALLOWED_REDIRECT_URIS allowlist'ine karşı doğrular (bkz.
    # AuthService.google_sign_in).
    redirect_uri: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class DeviceTokenRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


# ── Response DTO'ları ─────────────────────────────────────────────────────────

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class StatusResponse(BaseModel):
    """Genel amaçlı `{"status": "ok"}` yanıtı — `forgot-password`'ın
    (bkz. milestone'un kendi "generic success response" gereksinimi) VE
    `reset-password`'ın ortak dönüş şekli. Var olan `logout`/`device-token`
    route'ları zaten AYNI ham `{"status": "ok"}` sözlüğünü elle döndürüyordu
    (bkz. app/api/internal/auth.py) — burada yalnızca bunun için bir DTO
    ADI verildi, YENİ bir sözleşme İCAT EDİLMEDİ."""
    status: str = "ok"
