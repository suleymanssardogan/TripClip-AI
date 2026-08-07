"""
Application katmanı — video işleme tamamlandığında/başarısız olduğunda
kullanıcıya APNs push bildirimi gönderir.

iOS tarafı (AppDelegate.didReceive) bildirimdeki `video_id` alanını okuyup
kullanıcıyı doğrudan o videoya götürüyor — payload'daki anahtar bu yüzden
sabit tutulmalı.
"""
import logging
from typing import Optional

from app.domain.repositories.user_repository import AbstractUserRepository
from app.infrastructure.push.apns_client import ApnsClient, ApnsResult, get_apns_client

logger = logging.getLogger(__name__)


class PushService:

    def __init__(self, user_repo: AbstractUserRepository, apns_client: Optional[ApnsClient] = None):
        self._user_repo = user_repo
        self._apns = apns_client or get_apns_client()

    def notify_video_completed(self, video) -> None:
        stops = len(video.deduplicated_locations or [])
        title = "Gezin hazır! 🗺️"
        body  = f"{stops} mekan bulundu — hemen göz at." if stops else "Video işlendi, sonuçları gör."
        self._send(video, title, body)

    def notify_video_failed(self, video) -> None:
        title = "Video işlenemedi"
        body  = "Bir sorun oluştu — tekrar denemek ister misin?"
        self._send(video, title, body)

    def _send(self, video, title: str, body: str) -> None:
        if not video.user_id or not self._apns.is_configured:
            return

        user = self._user_repo.get_by_id(video.user_id)
        if not user or not user.apns_token:
            return

        result = self._apns.send(
            device_token=user.apns_token,
            title=title,
            body=body,
            data={"video_id": str(video.id)},
        )
        if result is ApnsResult.INVALID_TOKEN:
            logger.info("APNs token geçersiz, temizleniyor | user_id=%s", user.id)
            self._user_repo.clear_apns_token(user.id)
