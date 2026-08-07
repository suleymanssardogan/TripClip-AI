"""
Shared-trip büyüme hunisi için event taksonomisi — tek doğru kaynak.

`trip_id`, videolar-arası Trip Builder varlığına (app/models/trip.py) DEĞİL,
çalışan paylaşım sayfası olan Video/Plan'a işaret eder (bkz.
docs/analytics/shared-trip-events.md "Scope" bölümü) — Trip Builder'ın henüz
hiçbir paylaşım yeteneği yok, bu isimlendirme kullanıcıya dönük "gezi" dilini
yansıtıyor.

Her event burada tanımlı olsa da hepsi bir tetikleyiciye bağlı DEĞİL —
NOT_YET_WIRED_EVENTS'e bakın: bu üçü (davet/reddet/süre-doldu) ürünte
karşılığı olmayan, gelecekteki collaborative-trip özelliği (goal.md Phase 6,
v2) için şema uyumluluğu amacıyla tanımlanmış, sahte bir tetikleyiciye
bağlanmamış event'ler.
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
CLIENT_FIREABLE_EVENTS = frozenset({
    AnalyticsEvent.SHARED_TRIP_LINK_COPIED,
    AnalyticsEvent.SHARED_TRIP_SHARE_SHEET_OPENED,
    AnalyticsEvent.SHARED_TRIP_OPENED,
    AnalyticsEvent.SHARED_TRIP_JOINED,
})

# Taksonomide tanımlı ama hiçbir yerden tetiklenmiyor — ürünte davet/kabul/
# reddetme/süre-dolma mekanizması yok. Bkz. docs/analytics/shared-trip-events.md.
NOT_YET_WIRED_EVENTS = frozenset({
    AnalyticsEvent.SHARED_TRIP_INVITE_SENT,
    AnalyticsEvent.SHARED_TRIP_DECLINED,
    AnalyticsEvent.SHARED_TRIP_EXPIRED,
})
