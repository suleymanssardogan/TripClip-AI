"""
Shared-trip büyüme hunisi için event taksonomisi — tek doğru kaynak.

`trip_id` iki farklı varlık uzayını paylaşır — `kind` alanı hangisi olduğunu
ayırt eder (bkz. AnalyticsService.track):
  - `kind="video"` (varsayılan): çalışan paylaşım sayfası olan Video/Plan'a
    işaret eder (bkz. docs/shared-trip-analytics.md "Scope" bölümü).
  - `kind="trip"`: Trip Builder'ın `Trip` varlığına (app/models/trip.py)
    işaret eder — trip sharing (invite/accept/decline) bu uzayda çalışır.

Her event burada tanımlı olsa da hepsi bir tetikleyiciye bağlı değildir.
`shared_trip_invite_sent`/`declined`/`expired`, trip sharing'in
`SqlSharingRepository`'sinden (`kind="trip"` ile) tetiklenir. Kabul (accept)
için henüz karşılık gelen bir event YOK — `accept_by_token` hiçbir analytics
çağrısı yapmıyor; "davet kabul edildi" büyüme sinyali bugün gözlemlenemiyor
(bkz. docs/shared-trip-analytics.md).
"""
from enum import Enum


class AnalyticsEvent(str, Enum):
    SHARED_TRIP_CREATED             = "shared_trip_created"
    SHARED_TRIP_LINK_COPIED         = "shared_trip_link_copied"
    SHARED_TRIP_SHARE_SHEET_OPENED  = "shared_trip_share_sheet_opened"
    SHARED_TRIP_INVITE_SENT         = "shared_trip_invite_sent"
    SHARED_TRIP_OPENED              = "shared_trip_opened"
    SHARED_TRIP_JOINED              = "shared_trip_joined"
    SHARED_TRIP_DECLINED            = "shared_trip_declined"
    SHARED_TRIP_EXPIRED             = "shared_trip_expired"
    SHARED_TRIP_DELETED             = "shared_trip_deleted"


# İstemcinin (web/iOS) doğrudan beacon endpoint'i üzerinden gönderebileceği
# event'ler. CREATED ve DELETED bilerek dışarıda: bunlar sunucunun zaten
# kontrol ettiği durum değişikliklerinden türetiliyor — istemciden kabul
# edilirse herkes var olmayan bir "trip" için sahte olay üretebilirdi.
# INVITE_SENT/DECLINED/EXPIRED de dışarıda: bunlar da sunucu tarafından
# (SqlSharingRepository) tetiklenir — istemcinin doğrudan tetikleyebileceği
# bir kullanıcı eylemi değiller.
CLIENT_FIREABLE_EVENTS = frozenset({
    AnalyticsEvent.SHARED_TRIP_LINK_COPIED,
    AnalyticsEvent.SHARED_TRIP_SHARE_SHEET_OPENED,
    AnalyticsEvent.SHARED_TRIP_OPENED,
    AnalyticsEvent.SHARED_TRIP_JOINED,
})
