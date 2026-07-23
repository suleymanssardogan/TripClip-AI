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
    RefreshRequest,
    LogoutRequest,
    AuthResponse,
)
from app.application.services.auth_service import AuthService
from app.infrastructure.repositories.sql_user_repository import SqlUserRepository
from app.infrastructure.repositories.sql_refresh_token_repository import SqlRefreshTokenRepository


def _rate_limit_key(request: Request) -> str:
    """
    core-api yalnızca BFF'lerden (Docker internal network + INTERNAL_API_SECRET)
    çağrılır — gerçek istemci hiçbir zaman doğrudan buraya bağlanmaz. Bu yüzden
    request.client.host her zaman BFF container'ının adresidir: get_remote_address
    kullanılsaydı TÜM son kullanıcılar tek bir paylaşımlı kotayı tüketirdi (bir
    kullanıcının çok sayıda hatalı denemesi, aynı anda giriş yapan herkesi kilitler).
    BFF, gerçek istemci IP'sini X-Forwarded-For header'ı ile iletir (bkz.
    web-bff/mobile-bff routes/auth.py `_forward`) — varsa onu kullan, yoksa
    (örn. core-api'ye doğrudan istek atılan local geliştirme/test) eski davranışa düş.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


router  = APIRouter(prefix="/internal/auth", tags=["auth"])
limiter = Limiter(key_func=_rate_limit_key)


# ── Dependency Factory ────────────────────────────────────────────────────────

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    user_repo = SqlUserRepository(db)
    refresh_token_repo = SqlRefreshTokenRepository(db)
    return AuthService(user_repo, refresh_token_repo)


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
def apple_sign_in(
    request: Request,
    body: AppleSignInRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.apple_sign_in(
        identity_token=body.identity_token,
        full_name=body.full_name,
    )


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit("20/minute")
def refresh(
    request: Request,
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.refresh(body.refresh_token)


@router.post("/logout")
@limiter.limit("20/minute")
def logout(
    request: Request,
    body: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
):
    service.logout(body.refresh_token)
    return {"status": "ok"}
