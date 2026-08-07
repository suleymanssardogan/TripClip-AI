"""
Application katmanı — shared-trip büyüme hunisi event'lerinin kaydı.

Tek giriş noktası: diğer katmanlar (Celery task, VideoService, beacon route)
her zaman `track()` çağırır, hiçbir zaman MongoAnalyticsClient'a doğrudan
dokunmaz — döküman şekli (timestamp ekleme, alan adları) burada tek yerde
sabitlenir.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.analytics_events import AnalyticsEvent
from app.infrastructure.analytics.mongo_analytics_client import (
    MongoAnalyticsClient,
    get_analytics_mongo_client,
)

logger = logging.getLogger(__name__)


class AnalyticsService:

    def __init__(self, mongo_client: Optional[MongoAnalyticsClient] = None):
        self._mongo = mongo_client or get_analytics_mongo_client()

    def track(
        self,
        event: AnalyticsEvent,
        trip_id: int,
        platform: str,
        user_id: Optional[int] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Bir event'i kaydeder. Best-effort ve KESİNLİKLE fırlatmaz: MongoAnalyticsClient
        zaten kendi içinde hataları yutuyor (bkz. mongo_analytics_client.py),
        ama bu metod bunu spesifikasyonun "failures must never affect user
        requests" gereksinimi gereği kendi katmanında da garanti eder —
        çağıran taraf (Celery task, VideoService, HTTP beacon'ın background
        task'ı) bu çağrının asla patlamayacağına koşulsuz güvenebilir.
        """
        document = {
            "event":     event.value,
            "trip_id":   trip_id,
            "user_id":   user_id,
            "platform":  platform,
            "source":    source,
            "timestamp": datetime.now(timezone.utc),
            "metadata":  metadata or {},
        }
        try:
            self._mongo.record(document)
        except Exception:
            logger.exception("Analytics event kaydı başarısız (best-effort) | event=%s", event.value)


_default_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _default_service
    if _default_service is None:
        _default_service = AnalyticsService()
    return _default_service
