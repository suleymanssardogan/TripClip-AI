"""
Application katmanı — Auth iş mantığı.
Bağımlılıklar AbstractUserRepository üzerinden enjekte edilir → mock'lanabilir.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException
import httpx
import jwt as pyjwt
import logging

from app.domain.repositories.user_repository import AbstractUserRepository
from app.domain.repositories.refresh_token_repository import AbstractRefreshTokenRepository
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
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

    def __init__(self, user_repo: AbstractUserRepository, refresh_token_repo: AbstractRefreshTokenRepository):
        self._repo = user_repo
        self._refresh_repo = refresh_token_repo

    # ── Token issuance (register/login/apple/refresh ortak yolu) ─────────────

    def _issue_tokens(self, user, replaces: Optional[int] = None) -> AuthResponse:
        access_token = create_access_token(user.id, user.email)

        raw_refresh = generate_refresh_token()
        new_row = self._refresh_repo.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        if replaces is not None:
            self._refresh_repo.revoke(replaces, replaced_by_id=new_row.id)

        return AuthResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            user_id=user.id,
            email=user.email,
        )

    # ── Refresh / Logout ──────────────────────────────────────────────────────

    def refresh(self, raw_refresh_token: str) -> AuthResponse:
        stored = self._refresh_repo.get_by_hash(hash_refresh_token(raw_refresh_token))
        if not stored:
            raise AuthException("Geçersiz refresh token", code="REFRESH_TOKEN_INVALID")

        if stored.revoked_at is not None:
            # Zaten rotate edilmiş (veya iptal edilmiş) bir token tekrar sunuluyor —
            # çalıntı token kullanılmış olabilir sinyali. Tüm aileyi iptal et.
            self._refresh_repo.revoke_all_for_user(stored.user_id)
            raise AuthException(
                "Refresh token yeniden kullanıldı — güvenlik nedeniyle tüm oturumlar sonlandırıldı, tekrar giriş yapın",
                code="REFRESH_TOKEN_REUSED",
            )

        if stored.expires_at < datetime.utcnow():
            raise AuthException("Refresh token süresi doldu", code="REFRESH_TOKEN_EXPIRED")

        user = self._repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise AuthException("Kullanıcı bulunamadı", code="AUTH_ERROR")

        # Atomic claim — yukarıdaki `revoked_at is not None` kontrolü ile bu
        # nokta arasında başka bir eşzamanlı refresh isteği aynı token'ı
        # işleyip bitirmiş olabilir (read-then-write race). revoke_if_active
        # tek bir UPDATE...WHERE ile bunu kapatır: sadece BİR istek True alır.
        if not self._refresh_repo.revoke_if_active(stored.id):
            raise AuthException(
                "Bu refresh token az önce başka bir istek tarafından kullanıldı, lütfen tekrar deneyin",
                code="REFRESH_TOKEN_RACE_LOST",
            )

        return self._issue_tokens(user, replaces=stored.id)

    def logout(self, raw_refresh_token: str) -> None:
        stored = self._refresh_repo.get_by_hash(hash_refresh_token(raw_refresh_token))
        if stored and stored.revoked_at is None:
            self._refresh_repo.revoke(stored.id)

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

        return self._issue_tokens(user)

    def login(self, email: str, password: str) -> AuthResponse:
        # Case-insensitive + trim — iOS otomatik düzeltme/büyük harf kaynaklı
        # mismatch'leri önler. Production-grade auth pattern.
        normalized = (email or "").strip().lower()

        user = self._repo.get_by_email(normalized)
        if not user:
            # Fallback — eski kayıtlar büyük harfle saklanmış olabilir
            user = self._repo.get_by_email(email)

        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            # E-posta/şifre ve "kullanıcı bulundu mu" bilgisi kasıtlı olarak
            # loglanmıyor — loglar sızarsa hem PII ifşası hem de kullanıcı
            # numaralandırma (user enumeration) saldırı yüzeyi olurdu.
            import logging
            logging.getLogger("auth").warning("❌ LOGIN failed")
            raise AuthException("E-posta adresi veya şifre hatalı")

        return self._issue_tokens(user)

    # ── Apple Sign In ─────────────────────────────────────────────────────────
    #
    # Sync httpx.Client kullanılır (async değil): bu metod zaten senkron DB
    # çağrıları (self._repo.*) yapıyor — async/sync karışımı çıkarmak yerine
    # tamamen sync tutup FastAPI'nin route'u threadpool'da çalıştırmasına
    # bırakıyoruz (register/login/refresh/logout ile aynı, kanıtlanmış desen).
    # Apple Sign-In sık çağrılan bir yol değil, ekstra async karmaşıklığına değmez.

    def apple_sign_in(self, identity_token: str, full_name: str | None = None) -> AuthResponse:
        apple_user_id, email = self._verify_apple_token(identity_token)

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

        return self._issue_tokens(user)

    # ── Push Notifications ────────────────────────────────────────────────────

    def register_device_token(self, user_id: int, token: str) -> None:
        self._repo.update_apns_token(user_id, token)

    @staticmethod
    def _verify_apple_token(identity_token: str) -> tuple[str, str | None]:
        try:
            with httpx.Client() as client:
                resp = client.get(APPLE_KEYS_URL)
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
