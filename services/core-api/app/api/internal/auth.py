"""
Presentation katmanı — Auth route handler'ları.
Sadece: input al → service çağır → response döndür.
İş mantığı, DB sorguları, şifre hash'leme burada YOK.
"""
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional

from app.core.database import get_db
from app.application.dto.auth_dto import (
    RegisterRequest,
    LoginRequest,
    AppleSignInRequest,
    GoogleSignInRequest,
    RefreshRequest,
    LogoutRequest,
    DeviceTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    AuthResponse,
    StatusResponse,
)
from app.application.services.auth_service import AuthService
from app.infrastructure.repositories.sql_user_repository import SqlUserRepository
from app.infrastructure.repositories.sql_refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.repositories.sql_password_reset_token_repository import SqlPasswordResetTokenRepository
from app.infrastructure.email.email_service import EmailService


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
    reset_token_repo = SqlPasswordResetTokenRepository(db)
    return AuthService(user_repo, refresh_token_repo, reset_token_repo, EmailService())


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


@router.post("/forgot-password", response_model=StatusResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    """DAİMA `{"status": "ok"}` döner — hesap var olsun ya da olmasın (bkz.
    AuthService.request_password_reset'in kendi enumeration-direnci
    doc yorumu). Yalnızca ÇOK BASİT bir biçim kontrolü (boş string) burada
    yapılır; "geçerli e-posta formatı mı" gibi daha ayrıntılı bir doğrulama
    BİLEREK YAPILMAZ — böyle bir hata mesajı bile dolaylı bir enumeration
    sinyali OLABİLİRDİ, bu yüzden format ne olursa olsun aynı genel yanıt
    döner."""
    service.request_password_reset(body.email)
    return StatusResponse()


@router.post("/reset-password", response_model=StatusResponse)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    service.reset_password(raw_token=body.token, new_password=body.new_password)
    return StatusResponse()


@router.post("/google", response_model=AuthResponse)
@limiter.limit("5/minute")
def google_sign_in(
    request: Request,
    body: GoogleSignInRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.google_sign_in(code=body.code, redirect_uri=body.redirect_uri)


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


@router.put("/device-token")
def register_device_token(
    body: DeviceTokenRequest,
    service: AuthService = Depends(get_auth_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """BFF, kendi doğruladığı JWT'den çözdüğü user_id'yi x-user-id header'ı ile iletir."""
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    service.register_device_token(x_user_id, body.token)
    return {"status": "ok"}
