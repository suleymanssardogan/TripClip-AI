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
import os

from app.domain.repositories.user_repository import AbstractUserRepository
from app.domain.repositories.refresh_token_repository import AbstractRefreshTokenRepository
from app.domain.repositories.password_reset_token_repository import AbstractPasswordResetTokenRepository
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    generate_secure_token,
    hash_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.exceptions import (
    DuplicateEmailException,
    DuplicateUsernameException,
    AuthException,
    DatabaseException,
)
from app.application.dto.auth_dto import AuthResponse
from app.infrastructure.email.email_service import EmailService

logger = logging.getLogger(__name__)

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# M34 — şifre sıfırlama token'ının ömrü. Refresh token'lardan (30 gün) çok
# daha KISA tutuldu: bu bir OTURUM değil, tek seferlik bir "kimliğini
# e-posta erişiminle kanıtla" penceresi — sektör standardı 15dk-1sa arası;
# 30 dakika (refresh token akışının hiçbirinde kullanılmayan, TAMAMEN yeni
# bir değer) makul bir orta nokta.
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
# E-postadaki linkin işaret ettiği web sayfası — core-api hiçbir HTML
# RENDER ETMEZ (bkz. mevcut mimari: tüm UI Web/iOS'ta), yalnızca linki
# BURADAN kurar. Web reset-password sayfası ?token= query param'ını okur.
PASSWORD_RESET_URL_BASE = os.getenv("PASSWORD_RESET_URL_BASE", "http://localhost:3000/reset-password")


class AuthService:

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        refresh_token_repo: AbstractRefreshTokenRepository,
        reset_token_repo: AbstractPasswordResetTokenRepository,
        email_service: EmailService,
    ):
        self._repo = user_repo
        self._refresh_repo = refresh_token_repo
        self._reset_repo = reset_token_repo
        self._email = email_service

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

    # ── Şifre Sıfırlama (M34) ────────────────────────────────────────────────
    #
    # `RefreshToken`/`ShareToken` ile AYNI ilke: ham token asla DB'ye yazılmaz
    # (yalnızca hash'i), tek kullanımlık, süresi dolabilir (bkz.
    # app/models/password_reset_token.py). `login()`'in AYNI enumeration-
    # direnci ilkesi burada da geçerli: `request_password_reset` hesabın var
    # olup olmadığına göre FARKLI bir dış görünüm ASLA üretmez.

    def request_password_reset(self, email: str) -> None:
        """Her zaman `None` döner (başarı/başarısızlık dışarıdan AYIRT
        EDİLEMEZ) — e-posta var olsun ya da olmasın, aynı istek süresi/yanıtı
        (bkz. milestone Req "forgot-password request should return the same
        externally visible result for existing/non-existing accounts").
        Gerçek gönderim best-effort'tur; e-posta servisi yapılandırılmamışsa
        ya da gönderim başarısız olursa bile bu metod SESSİZCE başarılı gibi
        döner — hem enumeration direnci hem de var olan "opsiyonel altyapı
        deploy'u bozmaz" ilkesi (bkz. EmailService.is_configured) için."""
        normalized = (email or "").strip().lower()
        user = self._repo.get_by_email(normalized) or self._repo.get_by_email(email)

        if not user or not user.hashed_password:
            # Kullanıcı yok YA DA yalnızca Apple ile giriş yapan bir hesap
            # (hashed_password yok — sıfırlanacak bir şifresi bile yok).
            # İkisinde de SESSİZCE hiçbir şey yapmadan dön — dışarıdan
            # `request_password_reset("var-olan@mail.com")` ile
            # `request_password_reset("olmayan@mail.com")` AYIRT EDİLEMEZ.
            logger.info("Şifre sıfırlama istendi (hesap yok ya da şifresiz) — e-posta gönderilmedi.")
            return

        # Önceki, hâlâ kullanılmamış sıfırlama linkleri geçersiz kılınır —
        # her zaman EN SON istenen link geçerli olsun (bkz. repository'nin
        # kendi doc yorumu).
        self._reset_repo.invalidate_all_for_user(user.id)

        raw_token = generate_secure_token()
        self._reset_repo.create(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )

        reset_link = f"{PASSWORD_RESET_URL_BASE}?token={raw_token}"
        # DİKKAT: `raw_token`/`reset_link` HİÇBİR yerde loglanmaz — yalnızca
        # e-posta gövdesine (kullanıcının kendi gelen kutusuna) gider.
        self._email.send(
            to_email=user.email,
            subject="TripClip AI — Şifre Sıfırlama",
            body=(
                f"Merhaba {user.username or ''},\n\n"
                "TripClip AI hesabınız için bir şifre sıfırlama isteği aldık. "
                f"Şifrenizi sıfırlamak için aşağıdaki linke tıklayın (bu link "
                f"{PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} dakika içinde geçerliliğini yitirir):\n\n"
                f"{reset_link}\n\n"
                "Bu isteği siz yapmadıysanız bu e-postayı görmezden gelebilirsiniz; "
                "hesabınızda hiçbir değişiklik yapılmayacaktır."
            ),
        )
        # `.send()`'in dönüş değeri (gönderildi/gönderilemedi) BİLEREK
        # KULLANILMAZ — çağıran tarafa (route) hiçbir zaman yansıtılmaz,
        # aksi halde "e-posta gönderilemedi" ile "hesap yok" durumları
        # dışarıdan AYIRT EDİLEBİLİR hale gelirdi.

    def reset_password(self, raw_token: str, new_password: str) -> None:
        """Geçerli bir token + yeni şifre ile şifreyi günceller. Başarılı
        sıfırlama sonrası kullanıcının TÜM refresh token'ları (bkz.
        `revoke_all_for_user` — zaten var olan, refresh-token-reuse
        savunmasında kullanılan AYNI metod) iptal edilir — bu KULLANICININ
        KENDİ diğer oturumlarıdır, "unrelated users" DEĞİL (bkz. milestone
        Req "do not invalidate unrelated users/sessions unless the existing
        security architecture explicitly requires it") — şifresi
        sıfırlanan bir hesabın ele geçirilmiş olma ihtimaline karşı
        standart, iyi bilinen bir güvenlik pratiği."""
        stored = self._reset_repo.get_by_hash(hash_token(raw_token))
        if not stored:
            raise AuthException("Geçersiz ya da süresi dolmuş sıfırlama linki", code="PASSWORD_RESET_TOKEN_INVALID")

        if stored.used_at is not None:
            raise AuthException(
                "Bu sıfırlama linki zaten kullanılmış — yeni bir sıfırlama isteği gönderin",
                code="PASSWORD_RESET_TOKEN_USED",
            )

        if stored.expires_at < datetime.utcnow():
            raise AuthException("Sıfırlama linkinin süresi doldu — yeni bir sıfırlama isteği gönderin",
                                 code="PASSWORD_RESET_TOKEN_EXPIRED")

        user = self._repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise AuthException("Geçersiz ya da süresi dolmuş sıfırlama linki", code="PASSWORD_RESET_TOKEN_INVALID")

        # Atomic claim — `RefreshTokenRepository.revoke_if_active`'ın AYNI
        # race-safety ilkesi: aynı token'la eşzamanlı iki sıfırlama isteği
        # gelirse yalnızca biri gerçekten uygulanır.
        if not self._reset_repo.mark_used_if_active(stored.id):
            raise AuthException(
                "Bu sıfırlama linki az önce başka bir istek tarafından kullanıldı",
                code="PASSWORD_RESET_TOKEN_USED",
            )

        try:
            self._repo.update_password(user.id, hash_password(new_password))
        except Exception as exc:
            raise DatabaseException("reset_password", str(exc))

        self._refresh_repo.revoke_all_for_user(user.id)

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

    # ── Google Sign In (M34) ─────────────────────────────────────────────────
    #
    # Authorization-Code akışı, client secret YALNIZCA core-api'de: istemci
    # (Web/iOS) Google'ın KENDİ yetkilendirme ekranını açar (tarayıcı yönlendirmesi
    # / ASWebAuthenticationSession — platforma özgü, iş mantığı DEĞİL), geri
    # dönen TEK KULLANIMLIK kodu buraya gönderir. Kod-değişimi + id_token
    # doğrulaması `_verify_apple_token`'ın BİREBİR AYNI deseni (JWKS'ten
    # anahtar bul, imzayı doğrula) — Apple'ın AKSİNE Google id_token'ı
    # DOĞRUDAN vermiyor, önce bir kod-değişimi GEREKİYOR (bkz.
    # `_exchange_and_verify_google_code`).

    def google_sign_in(self, code: str, redirect_uri: str) -> AuthResponse:
        self._validate_google_redirect_uri(redirect_uri)
        google_user_id, email, email_verified, name = self._exchange_and_verify_google_code(code, redirect_uri)

        user = self._repo.get_by_google_id(google_user_id)

        if not user and email and email_verified:
            # Var olan bir e-posta/şifre hesabıyla AYNI, Google tarafından
            # DOĞRULANMIŞ e-posta — güvenle BAĞLA (bkz. milestone Req 3
            # "existing email/password account with same verified email →
            # account linking"). `email_verified` FALSE ise bu adım hiç
            # ÇALIŞMAZ — doğrulanmamış bir e-postayla ASLA otomatik hesap
            # birleştirme YAPILMAZ (bkz. milestone'un kendi AÇIK uyarısı).
            user = self._repo.get_by_email(email)

        if not user:
            if not email:
                raise HTTPException(status_code=400, detail="Email required for first-time Google Sign In")
            if self._repo.get_by_email(email):
                # E-posta zaten BAŞKA bir hesapta var ama Google onu
                # DOĞRULANMAMIŞ olarak bildirdi — yukarıdaki adım bu yüzden
                # BAĞLAMADI. Aynı e-postayla ikinci bir hesap da
                # OLUŞTURULAMAZ (User.email unique) — güvenli başarısızlık:
                # kullanıcı normal (e-posta/şifre ya da doğrulanmış Google)
                # girişe yönlendirilir, hiçbir hesap sessizce birleştirilmez
                # ya da bir DB constraint hatasıyla ÇÖKÜLMEZ.
                raise AuthException(
                    "Bu e-posta adresiyle zaten bir hesap var ama Google e-postanızı doğrulanmış olarak "
                    "bildirmedi. Lütfen normal giriş yapın.",
                    code="GOOGLE_EMAIL_NOT_VERIFIED",
                )
            user = self._repo.create(
                email=email,
                username=name or email.split("@")[0],
                google_id=google_user_id,
            )
        elif not user.google_id:
            self._repo.update_google_id(user.id, google_user_id)

        return self._issue_tokens(user)

    @staticmethod
    def _validate_google_redirect_uri(redirect_uri: str) -> None:
        """İstemcinin bildirdiği `redirect_uri`'yi bir allowlist'e karşı
        doğrular — aksi halde bir saldırgan, koda erişebildiği KEYFİ bir
        redirect_uri ile core-api'yi Google'a karşı kandırmaya
        çalışabilirdi (open-redirect-benzeri bir OAuth riski)."""
        allowed = [u.strip() for u in os.getenv("GOOGLE_ALLOWED_REDIRECT_URIS", "").split(",") if u.strip()]
        if not allowed or redirect_uri not in allowed:
            raise AuthException("Google ile giriş şu anda yapılandırılmamış", code="GOOGLE_AUTH_UNAVAILABLE")

    @staticmethod
    def _exchange_and_verify_google_code(code: str, redirect_uri: str) -> tuple[str, Optional[str], bool, Optional[str]]:
        """Döner: `(google_user_id, email, email_verified, name)`.

        `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` eksikse Google Sign-In
        SESSİZCE devre dışı kabul edilir (bkz. bu dosyanın kendi "opsiyonel
        altyapı deploy'u bozmaz" ilkesi — ApnsClient/EmailService ile AYNI)."""
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise AuthException("Google ile giriş şu anda yapılandırılmamış", code="GOOGLE_AUTH_UNAVAILABLE")

        try:
            with httpx.Client() as client:
                token_resp = client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    timeout=10,
                )
                if token_resp.status_code != 200:
                    raise HTTPException(status_code=401, detail="Google authorization code exchange failed")

                raw_id_token = token_resp.json().get("id_token")
                if not raw_id_token:
                    raise HTTPException(status_code=401, detail="Google response missing id_token")

                jwks_resp = client.get(GOOGLE_JWKS_URL, timeout=10)
                jwks = jwks_resp.json()

            header = pyjwt.get_unverified_header(raw_id_token)
            key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
            if not key:
                raise HTTPException(status_code=401, detail="Google key not found")

            public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key)
            payload = pyjwt.decode(raw_id_token, public_key, algorithms=["RS256"], audience=client_id)

            # `issuer=` parametresiyle DEĞİL, elle kontrol edilir — Google
            # iss claim'i sürüme göre "https://accounts.google.com" ya da
            # "accounts.google.com" olabilir, ikisi de GEÇERLİDİR.
            if payload.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
                raise HTTPException(status_code=401, detail="Unexpected Google token issuer")

            return (
                payload["sub"],
                payload.get("email"),
                bool(payload.get("email_verified", False)),
                payload.get("name"),
            )

        except HTTPException:
            raise
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Google token expired")
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid Google credential")

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
