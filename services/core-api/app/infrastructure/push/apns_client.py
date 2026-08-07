"""
Infrastructure katmanı — Apple Push Notification service (APNs) HTTP/2 istemcisi.

Provider-token (JWT/ES256) tabanlı kimlik doğrulama kullanır — sertifika
tabanlı eski yönteme göre daha basit: token kendisi ~1 saat geçerli, ayrı bir
sertifika yenileme süreci gerekmez.

Yapılandırma (celery-worker ortam değişkenleri):
    APNS_KEY_ID       — .p8 anahtarının Key ID'si (Apple Developer > Keys)
    APNS_TEAM_ID      — Apple Developer Team ID
    APNS_BUNDLE_ID    — iOS app bundle identifier (apns-topic başlığı için)
    APNS_AUTH_KEY     — .p8 dosyasının PEM içeriği (env'de tek satır, \\n kaçışlı)
    APNS_USE_SANDBOX  — "true" ise development gateway'i kullanılır (varsayılan: true)

Herhangi biri eksikse istemci `is_configured=False` olur ve PushService
sessizce no-op yapar — eksik kimlik bilgisi deploy'u bozmaz (bkz. CLAUDE.md:
SENTRY_DSN aynı "yalnızca set edilirse aktif" deseni).
"""
import enum
import logging
import os
import time
from typing import Optional

import httpx
import jwt

logger = logging.getLogger(__name__)

_PROD_HOST    = "https://api.push.apple.com"
_SANDBOX_HOST = "https://api.sandbox.push.apple.com"

# Apple: provider token 60 dakikaya kadar geçerli ama 20 dakikadan daha sık
# üretilmemesi öneriliyor — 50 dakikada bir yenileyip aradaki isteklerde
# aynı token'ı yeniden kullanıyoruz.
_TOKEN_TTL_SECONDS = 50 * 60


class ApnsResult(enum.Enum):
    SENT          = "sent"
    # BadDeviceToken / Unregistered (410) — token artık geçersiz, temizlenmeli.
    INVALID_TOKEN = "invalid_token"
    # Ağ hatası, 5xx, ya da istemci yapılandırılmamış — token'a dokunulmaz,
    # bir sonraki video tamamlandığında tekrar denenir.
    FAILED        = "failed"


class ApnsClient:

    def __init__(self):
        self._key_id    = os.getenv("APNS_KEY_ID")
        self._team_id   = os.getenv("APNS_TEAM_ID")
        self._bundle_id = os.getenv("APNS_BUNDLE_ID")
        raw_key = os.getenv("APNS_AUTH_KEY")
        self._auth_key = raw_key.replace("\\n", "\n") if raw_key else None
        self._sandbox = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"
        self._host = _SANDBOX_HOST if self._sandbox else _PROD_HOST

        self._cached_jwt: Optional[str] = None
        self._cached_jwt_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self._key_id and self._team_id and self._bundle_id and self._auth_key)

    def _provider_token(self) -> str:
        now = time.time()
        if self._cached_jwt and (now - self._cached_jwt_at) < _TOKEN_TTL_SECONDS:
            return self._cached_jwt

        token = jwt.encode(
            {"iss": self._team_id, "iat": int(now)},
            self._auth_key,
            algorithm="ES256",
            headers={"kid": self._key_id},
        )
        self._cached_jwt    = token
        self._cached_jwt_at = now
        return token

    def send(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> ApnsResult:
        if not self.is_configured:
            return ApnsResult.FAILED

        payload = {
            "aps": {"alert": {"title": title, "body": body}, "sound": "default"},
            **(data or {}),
        }
        headers = {
            "authorization":  f"bearer {self._provider_token()}",
            "apns-topic":      self._bundle_id,
            "apns-push-type":  "alert",
            "apns-priority":   "10",
        }

        try:
            with httpx.Client(http2=True, timeout=10.0) as client:
                resp = client.post(
                    f"{self._host}/3/device/{device_token}",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.warning("APNs isteği başarısız (ağ): %s", exc)
            return ApnsResult.FAILED

        if resp.status_code == 200:
            return ApnsResult.SENT

        reason = ""
        try:
            reason = resp.json().get("reason", "")
        except Exception:
            pass

        if resp.status_code == 410 or reason in {"BadDeviceToken", "Unregistered"}:
            logger.info("APNs geçersiz token | reason=%s", reason)
            return ApnsResult.INVALID_TOKEN

        logger.warning("APNs push başarısız | status=%s | reason=%s", resp.status_code, reason)
        return ApnsResult.FAILED


_default_client: Optional[ApnsClient] = None


def get_apns_client() -> ApnsClient:
    """Worker process başına tek istemci — provider JWT cache'ini paylaşır."""
    global _default_client
    if _default_client is None:
        _default_client = ApnsClient()
    return _default_client
