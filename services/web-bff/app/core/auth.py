"""
Web BFF — JWT kimlik doğrulama yardımcısı.
Core API ile aynı SECRET_KEY + algoritma kullanır.
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import os

_DEFAULT_SECRET = "tripclip-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", _DEFAULT_SECRET)
if os.getenv("APP_ENV") == "production" and len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters in production.")
ALGORITHM  = "HS256"

if SECRET_KEY == _DEFAULT_SECRET:
    import logging as _logging
    _logging.getLogger("web-bff.auth").warning(
        "⚠️  JWT_SECRET_KEY is using the insecure default value. "
        "Set JWT_SECRET_KEY in your environment before deploying."
    )
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must not be the default value in production."
        )

bearer_scheme = HTTPBearer(auto_error=False)
ACCESS_COOKIE = "tripclip_access"
REFRESH_COOKIE = "tripclip_refresh"


def get_access_claims(request: Request, credentials: HTTPAuthorizationCredentials | None = None) -> dict:
    token = request.cookies.get(ACCESS_COOKIE) or (credentials.credentials if credentials else None)
    if not token:
        raise HTTPException(status_code=401, detail="Kimlik doğrulama gerekli")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access" or not payload.get("sub"):
            raise ValueError("Geçersiz token türü")
        int(payload["sub"])
        return payload
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token")


def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    """
    HttpOnly access cookie veya eski Bearer header'ından user_id döndürür.
    Token yoksa veya geçersizse 401 fırlatır.
    """
    return int(get_access_claims(request, credentials)["sub"])


def get_optional_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int | None:
    """
    Token varsa user_id döndürür, yoksa None.
    Public endpoint'ler için kullanılır (keşif sayfası vb.).
    """
    if not request.cookies.get(ACCESS_COOKIE) and not credentials:
        return None
    try:
        return int(get_access_claims(request, credentials)["sub"])
    except HTTPException:
        return None
