"""
Infrastructure katmanı — SMTP tabanlı e-posta gönderimi (M34, şifre sıfırlama).

`ApnsClient` (app/infrastructure/push/apns_client.py) ile BİREBİR AYNI
"yalnızca yapılandırılmışsa aktif" deseni: `SMTP_HOST`/`SMTP_USER`/
`SMTP_PASSWORD` ayarlanmamışsa `is_configured` False olur, `send()` sessizce
`False` döner — eksik kimlik bilgisi deploy'u BOZMAZ (bkz. CLAUDE.md:
SENTRY_DSN'in AYNI "yalnızca set edilirse aktif" deseni).

Kullanılabilir tek bir e-posta gönderme mekanizması core-api'de daha önce
YOKTU (bkz. M34 inceleme raporu) — `smtplib` (Python standart kütüphanesi,
YENİ bir bağımlılık GEREKMEDİ) ile en küçük, üretime uygun implementasyon.

GÜVENLİK: `send()` ASLA alıcı e-postasını, konuyu (M34'te konu zaten geneldir
ama yine de) ya da gövdeyi (sıfırlama LİNKİNİ/token'ı İÇEREBİLİR) loglamaz —
yalnızca başarı/başarısızlık + istisna TİPİ (bkz. AuthService'in kendi
"parola/email loglanmaz" ilkesi, auth_service.py login()'in AYNI yaklaşımı).
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailService:

    def __init__(self):
        self._host = os.getenv("SMTP_HOST")
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._user = os.getenv("SMTP_USER")
        self._password = os.getenv("SMTP_PASSWORD")
        self._from_email = os.getenv("SMTP_FROM_EMAIL", "no-reply@tripclip.app")

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._user and self._password)

    def send(self, to_email: str, subject: str, body: str) -> bool:
        """Düz metin bir e-posta gönderir. Yapılandırılmamışsa ya da
        gönderim başarısız olursa `False` döner, ASLA fırlatmaz — çağıran
        taraf (`AuthService.request_password_reset`) bunu enumeration-resistant
        genel yanıtını ETKİLEMEDEN ele alır (bkz. milestone Req "forgot-password
        request should return the same externally visible result")."""
        if not self.is_configured:
            logger.info("EmailService yapılandırılmamış (SMTP_HOST/SMTP_USER/SMTP_PASSWORD eksik) — e-posta gönderilmedi.")
            return False

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self._from_email
            msg["To"] = to_email

            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._from_email, [to_email], msg.as_string())

            logger.info("E-posta başarıyla gönderildi.")
            return True
        except Exception as exc:
            logger.warning("E-posta gönderilemedi: %s", type(exc).__name__)
            return False
