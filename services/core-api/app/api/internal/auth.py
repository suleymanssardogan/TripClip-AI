from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.auth import hash_password, verify_password, create_access_token
from app.models.user import User
import httpx
import jwt as pyjwt
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal/auth", tags=["auth"])

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


# --- Email/Password ---

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="E-posta zaten kayıtlı")

    if body.username and db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Kullanıcı adı zaten alınmış")

    user = User(
        email=body.email,
        username=body.username or body.email.split("@")[0],
        hashed_password=hash_password(body.password),
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Kayıt işlemi sırasında bir hata oluştu")

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


# --- Apple Sign In ---

@router.post("/apple", response_model=AuthResponse)
async def apple_sign_in(body: AppleSignInRequest, db: Session = Depends(get_db)):
    apple_user_id, email = await _verify_apple_token(body.identity_token)

    # Var olan kullanıcıyı bul veya oluştur
    user = db.query(User).filter(User.apple_id == apple_user_id).first()

    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        if not email:
            raise HTTPException(status_code=400, detail="Email required for first-time Apple Sign In")
        user = User(
            email=email,
            username=body.full_name or email.split("@")[0],
            apple_id=apple_user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.apple_id:
        user.apple_id = apple_user_id
        db.commit()

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


async def _verify_apple_token(identity_token: str) -> tuple[str, str | None]:
    """Apple identity token'ı doğrula, (apple_user_id, email) döndür"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(APPLE_KEYS_URL)
            jwks = resp.json()

        header = pyjwt.get_unverified_header(identity_token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if not key:
            raise HTTPException(status_code=401, detail="Apple key not found")

        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key)
        payload = pyjwt.decode(
            identity_token,
            public_key,
            algorithms=["RS256"],
            audience="com.sardogan.TripClipAI",
        )
        return payload["sub"], payload.get("email")

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Apple token expired")
    except Exception as e:
        logger.error(f"Apple token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Apple token")
