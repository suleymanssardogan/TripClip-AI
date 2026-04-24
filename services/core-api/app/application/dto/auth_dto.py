"""
Auth DTO'ları — API request/response şemaları.
Route handler'lar sadece bu modelleri görür; DB modelleri görünmez.
"""
from pydantic import BaseModel
from typing import Optional


# ── Request DTO'ları ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str       # EmailStr yerine str — test/prod tüm domain'lerde çalışır
    password: str
    username: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: Optional[str] = None


# ── Response DTO'ları ─────────────────────────────────────────────────────────

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
