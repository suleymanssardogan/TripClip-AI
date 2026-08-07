"""
Infrastructure katmanı — analytics event'lerinin MongoDB'ye yazılması.

MongoDB zaten provision edilmiş (MONGODB_URL, docker-compose.yml) ama hiçbir
uygulama kodu ona bağlanmıyordu — CLAUDE.md'de "secondary storage" olarak
belgeli, bu ilk gerçek kullanımı.

Tamamen opsiyonel/best-effort: yazma başarısız olursa (Mongo erişilemez,
ANALYTICS_ENABLED=false vb.) sessizce loglar ve döner — hiçbir zaman
exception fırlatmaz. Aynı "yalnızca mevcutsa aktif, hata asla kullanıcı
isteğini etkilemez" felsefesi ApnsClient ve QdrantService ile paylaşılıyor.
"""
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "analytics_events"


class MongoAnalyticsClient:

    def __init__(self):
        self._client = None
        self._collection = None
        # Operasyonel kill-switch — deploy gerektirmeden kapatılabilir
        # (bkz. SENTRY_DSN/APNS_* ile aynı "yalnızca yapılandırılmışsa aktif" deseni).
        self.enabled = os.getenv("ANALYTICS_ENABLED", "true").lower() == "true"

    def _load(self):
        if self._collection is not None:
            return

        from pymongo import MongoClient

        url = os.getenv("MONGODB_URL")
        if not url:
            raise RuntimeError("MONGODB_URL ayarlanmamış")

        # Kısa server selection timeout: Mongo erişilemezse istek/task uzun
        # süre beklemeden hızlıca fail-open'a düşsün.
        client = MongoClient(url, serverSelectionTimeoutMS=3000)
        self._collection = client.get_default_database()[_COLLECTION_NAME]
        self._client = client

    def record(self, document: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        try:
            self._load()
            self._collection.insert_one(dict(document))
        except Exception as exc:
            logger.warning("Analytics event yazılamadı: %s", exc)


_default_client: Optional[MongoAnalyticsClient] = None


def get_analytics_mongo_client() -> MongoAnalyticsClient:
    """Worker/process başına tek istemci — Mongo bağlantısını paylaşır."""
    global _default_client
    if _default_client is None:
        _default_client = MongoAnalyticsClient()
    return _default_client
