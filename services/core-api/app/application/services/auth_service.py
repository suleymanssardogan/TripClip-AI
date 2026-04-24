"""
Application katmanı — Auth iş mantığı.
Bağımlılıklar AbstractUserRepository üzerinden enjekte edilir → mock'lanabilir.
"""
from fastapi import HTTPException
import httpx
import jwt as pyjwt
import logging

from app.domain.repositories.user_repository import AbstractUserRepository
from app.core.auth import hash_password, verify_password, create_access_token
from app.core.exceptions import (
    DuplicateEmailException,
    DuplicateUsernameException,
    AuthException,
    DatabaseException,
)
from app.application.dto.auth_dto import AuthResponse

logger = logging.getLogger(__name__)

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


class AuthService:

    def __init__(self, user_repo: AbstractUserRepository):
        self._repo = user_repo

    # ── Email/Password ────────────────────────────────────────────────────────

    def register(self, email: str, password: str, username: str | None = None) -> AuthResponse:
        if self._repo.get_by_email(email):
            raise DuplicateEmailException(email)

        resolved_username = username or email.split("@")[0]
        if self._repo.get_by_username(resolved_username):
            raise DuplicateUsernameException(resolved_username)

        try:
            user = self._repo.create(
                email=email,
                username=resolved_username,
                hashed_password=hash_password(password),
            )
        except Exception as exc:
            raise DatabaseException("register", str(exc))

        token = create_access_token(user.id, user.email)
        return AuthResponse(access_token=token, user_id=user.id, email=user.email)

    def login(self, email: str, password: str) -> AuthResponse:
        user = self._repo.get_by_email(email)
        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            raise AuthException("E-posta adresi veya şifre hatalı")

        token = create_access_token(user.id, user.email)
        return AuthResponse(access_token=token, user_id=user.id, email=user.email)

    # ── Apple Sign In ─────────────────────────────────────────────────────────

    async def apple_sign_in(self, identity_token: str, full_name: str | None = None) -> AuthResponse:
        apple_user_id, email = await self._verify_apple_token(identity_token)

        user = self._repo.get_by_apple_id(apple_user_id)
        if not user and email:
            user = self._repo.get_by_email(email)

        if not user:
            if not email:
                raise HTTPException(status_code=400, detail="Email required for first-time Apple Sign In")
            user = self._repo.create(
                email=email,
                username=full_name or email.split("@")[0],
                apple_id=apple_user_id,
            )
        elif not user.apple_id:
            self._repo.update_apple_id(user.id, apple_user_id)

        token = create_access_token(user.id, user.email)
        return AuthResponse(access_token=token, user_id=user.id, email=user.email)

    @staticmethod
    async def _verify_apple_token(identity_token: str) -> tuple[str, str | None]:
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
