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

`shared_trip_itinerary_applied` (`kind="trip"`), `SqlOptimizationRepository.
apply_itinerary`'den tetiklenir — bir kayıtlı optimizer sonucunun Trip'in
kanonik TripStop'una yazıldığı an (bkz. docs/trip-optimizer.md "Apply
semantics"). Taksonomideki hiçbir mevcut event bunu karşılamıyor:
INVITE_SENT/DECLINED/EXPIRED collaboration akışıyla ilgili, CREATED/DELETED
Video/Plan (kind="video") kind'inde ve tamamen farklı bir yaşam döngüsü
adımını temsil ediyor — "bir itinerary Trip'e uygulandı" hiçbirinin
yeniden yorumlanmış hali değil, gerçekten yeni bir eylem.

`shared_trip_itinerary_apply_undone` (`kind="trip"`), `SqlOptimizationRepository.
undo_apply_history`'den tetiklenir — `SHARED_TRIP_ITINERARY_APPLIED` ile
BİREBİR aynı gerekçeyle (Apply History & Undo milestone'u, bkz.
docs/trip-optimizer.md): "bir apply geri alındı" ne var olan bir event'in
yeniden yorumu, ne de ITINERARY_APPLIED'ın kendisi (tersi bir eylem, ayrı
bir olay) — kendi event'ini hak ediyor. Aynı sebeplerle server-only.
"""
from enum import Enum


class AnalyticsEvent(str, Enum):
    SHARED_TRIP_CREATED               = "shared_trip_created"
    SHARED_TRIP_LINK_COPIED           = "shared_trip_link_copied"
    SHARED_TRIP_SHARE_SHEET_OPENED    = "shared_trip_share_sheet_opened"
    SHARED_TRIP_INVITE_SENT           = "shared_trip_invite_sent"
    SHARED_TRIP_OPENED                = "shared_trip_opened"
    SHARED_TRIP_JOINED                = "shared_trip_joined"
    SHARED_TRIP_DECLINED              = "shared_trip_declined"
    SHARED_TRIP_EXPIRED               = "shared_trip_expired"
    SHARED_TRIP_DELETED               = "shared_trip_deleted"
    SHARED_TRIP_ITINERARY_APPLIED     = "shared_trip_itinerary_applied"
    SHARED_TRIP_ITINERARY_APPLY_UNDONE = "shared_trip_itinerary_apply_undone"


# İstemcinin (web/iOS) doğrudan beacon endpoint'i üzerinden gönderebileceği
# event'ler. CREATED ve DELETED bilerek dışarıda: bunlar sunucunun zaten
# kontrol ettiği durum değişikliklerinden türetiliyor — istemciden kabul
# edilirse herkes var olmayan bir "trip" için sahte olay üretebilirdi.
# INVITE_SENT/DECLINED/EXPIRED de dışarıda: bunlar da sunucu tarafından
# (SqlSharingRepository) tetiklenir — istemcinin doğrudan tetikleyebileceği
# bir kullanıcı eylemi değiller. ITINERARY_APPLIED de aynı gerekçeyle
# dışarıda: apply, sunucunun kendi TripStop mutasyonunun bir sonucu —
# istemciden kabul edilirse gerçekleşmemiş bir "apply" sahte biçimde
# raporlanabilirdi. ITINERARY_APPLY_UNDONE aynı sebeple dışarıda —
# `SqlOptimizationRepository.undo_apply_history`'nin kendi başarılı
# mutasyonunun bir sonucu, istemcinin doğrudan tetikleyebileceği bir olay
# değil.
CLIENT_FIREABLE_EVENTS = frozenset({
    AnalyticsEvent.SHARED_TRIP_LINK_COPIED,
    AnalyticsEvent.SHARED_TRIP_SHARE_SHEET_OPENED,
    AnalyticsEvent.SHARED_TRIP_OPENED,
    AnalyticsEvent.SHARED_TRIP_JOINED,
})
