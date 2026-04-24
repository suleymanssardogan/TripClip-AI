"""
Presentation katmanı — Auth route handler'ları.
Sadece: input al → service çağır → response döndür.
İş mantığı, DB sorguları, şifre hash'leme burada YOK.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.application.dto.auth_dto import (
    RegisterRequest,
    LoginRequest,
    AppleSignInRequest,
    AuthResponse,
)
from app.application.services.auth_service import AuthService
from app.infrastructure.repositories.sql_user_repository import SqlUserRepository

router = APIRouter(prefix="/internal/auth", tags=["auth"])


# ── Dependency Factory ────────────────────────────────────────────────────────
# FastAPI'nin DI sistemi: test ortamında override edilebilir.

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    user_repo = SqlUserRepository(db)
    return AuthService(user_repo)


# ── Route Handler'lar (ince) ──────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.register(
        email=body.email,
        password=body.password,
        username=body.username,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.login(email=body.email, password=body.password)


@router.post("/apple", response_model=AuthResponse)
async def apple_sign_in(
    body: AppleSignInRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.apple_sign_in(
        identity_token=body.identity_token,
        full_name=body.full_name,
    )
