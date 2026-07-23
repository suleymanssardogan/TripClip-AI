"""
Auth DTO'ları — API request/response şemaları.
Route handler'lar sadece bu modelleri görür; DB modelleri görünmez.
"""
from pydantic import BaseModel, field_validator
from typing import Optional


# ── Request DTO'ları ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str       # EmailStr yerine str — test/prod tüm domain'lerde çalışır
    password: str
    username: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # Yalnızca kayıtta uygulanır (login'de değil) — mevcut kullanıcıların
        # eski şifreleriyle giriş yapamaz hale gelmemesi için.
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ── Response DTO'ları ─────────────────────────────────────────────────────────

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
