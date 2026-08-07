"""
Presentation katmanı — shared-trip büyüme hunisi event beacon'ı.
Sadece: doğrula → arka planda kaydet → hemen dön. İş mantığını değiştirmez,
yalnızca gözlemler.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Header
from typing import Optional

from app.application.dto.analytics_dto import TrackEventRequest
from app.application.services.analytics_service import AnalyticsService, get_analytics_service
from app.core.analytics_events import AnalyticsEvent, CLIENT_FIREABLE_EVENTS
from app.core.exceptions import InvalidAnalyticsEventException

router = APIRouter(prefix="/internal/analytics", tags=["internal"])


def get_analytics_service_dep() -> AnalyticsService:
    return get_analytics_service()


@router.post("/events", status_code=202)
def track_event(
    body: TrackEventRequest,
    background_tasks: BackgroundTasks,
    service: AnalyticsService = Depends(get_analytics_service_dep),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    İstemciden (web/iOS) ateşlenen shared-trip event'lerini kaydeder.

    202 hemen döner — gerçek yazma `BackgroundTasks` ile yanıt gönderildikten
    SONRA çalışır, bu yüzden Mongo yavaş/erişilemez olsa bile istek asla
    yavaşlamaz ya da başarısız olmaz (bkz. AnalyticsService.track, zaten
    kendi içinde best-effort).

    `user_id` gövdeden değil BFF'in ilettiği x-user-id header'ından alınır —
    diğer internal endpoint'lerle aynı desen, istemcinin başka bir kullanıcı
    adına sahte event üretmesini engeller. Anonim ziyaretçiler (ör. herkese
    açık bir paylaşım sayfasını açan, giriş yapmamış biri) için None kalır —
    spesifikasyonun "user_id (when available)" gereksinimi bu.
    """
    try:
        event = AnalyticsEvent(body.event)
    except ValueError:
        raise InvalidAnalyticsEventException(f"Bilinmeyen event: '{body.event}'.")

    if event not in CLIENT_FIREABLE_EVENTS:
        raise InvalidAnalyticsEventException(
            f"'{body.event}' yalnızca sunucu tarafından tetiklenir, istemciden gönderilemez."
        )

    background_tasks.add_task(
        service.track,
        event=event,
        trip_id=body.trip_id,
        platform=body.platform,
        user_id=x_user_id,
        source=body.source,
        metadata=body.metadata,
    )
    return {"success": True}
