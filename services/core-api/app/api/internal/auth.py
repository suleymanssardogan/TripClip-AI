"""
Presentation katmanı — Auth route handler'ları.
Sadece: input al → service çağır → response döndür.
İş mantığı, DB sorguları, şifre hash'leme burada YOK.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.application.dto.auth_dto import (
    RegisterRequest,
    LoginRequest,
    AppleSignInRequest,
    AuthResponse,
)
from app.application.services.auth_service import AuthService
from app.infrastructure.repositories.sql_user_repository import SqlUserRepository

router  = APIRouter(prefix="/internal/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


# ── Dependency Factory ────────────────────────────────────────────────────────

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    user_repo = SqlUserRepository(db)
    return AuthService(user_repo)


# ── Route Handler'lar ─────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
@limiter.limit("10/minute")
def register(
    request: Request,
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.register(
        email=body.email,
        password=body.password,
        username=body.username,
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.login(email=body.email, password=body.password)


@router.post("/apple", response_model=AuthResponse)
@limiter.limit("5/minute")
async def apple_sign_in(
    request: Request,
    body: AppleSignInRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.apple_sign_in(
        identity_token=body.identity_token,
        full_name=body.full_name,
    )
