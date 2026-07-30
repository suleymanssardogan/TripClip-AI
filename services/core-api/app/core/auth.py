from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import hashlib
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
import os

_DEFAULT_SECRET = "tripclip-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", _DEFAULT_SECRET)
ALGORITHM = "HS256"

if SECRET_KEY == _DEFAULT_SECRET:
    import logging as _logging
    _logging.getLogger("tripclip.auth").warning(
        "⚠️  JWT_SECRET_KEY is using the insecure default value. "
        "Set JWT_SECRET_KEY in your environment before deploying."
    )
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must not be the default value in production. "
            "Set a secure random value via the JWT_SECRET_KEY environment variable."
        )
# Access token kısa ömürlü — çalıntı bir token'ın kullanım penceresini daraltır.
# Uzun ömürlü oturum, döndürülebilir/iptal edilebilir refresh token ile sağlanır
# (bkz. generate_refresh_token/hash_refresh_token + RefreshToken modeli).
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire, "type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    from app.models.user import User
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── Refresh Token — opak (JWT değil), DB'de hash'lenmiş halde saklanır ────────
#
# Neden opak? Bir JWT refresh token kullansaydık yine de iptal etmek için bir
# DB/blacklist kontrolüne ihtiyaç duyardık — opak + DB-backed, ekstra karmaşıklık
# katmadan aynı garantiyi (rotation + revocation) verir.

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
