from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Index
from app.core.database import Base
from datetime import datetime


class TripItineraryApplyHistory(Base):
    """
    Bir Trip'e uygulanan (ya da geri alınan) HER bir TripStop değişikliğinin
    kalıcı kaydı — bkz. docs/trip-optimizer.md "Apply History & Undo".
    `Trip.applied_itinerary_id`/`itinerary_applied_at` yalnızca "şu an ne
    uygulanmış" sorusuna cevap verir; bu tablo "hangi sırayla, ne zaman,
    kim tarafından" sorusuna da cevap verir.

    Her satır TEK bir başarılı olayı temsil eder — bir normal "Uygula"
    (`is_undo=False`) ya da bir "Geri Al" (`is_undo=True`); ikisi de AYNI
    şekilde modellenir (biri diğerinin özel durumu değil): her ikisi de
    TripStop'u SİLİP-YENİDEN-EKLER, her ikisi de kendi `previous_stops`/
    `previous_itinerary_id`'sini (bu olaydan HEMEN ÖNCEki durumun anlık
    görüntüsü) taşır. Bu simetri sayesinde bir "geri al"ın KENDİSİ de
    (eğer en son kayıtsa) geri alınabilir — bu, kazayla yapılan bir "Geri
    Al"ı düzeltmenin doğal, özel-durum GEREKTİRMEYEN yoludur.

    `previous_stops`: bu olaydan HEMEN ÖNCE TripStop'ta ne vardıysa, onun
    tam anlık görüntüsü — yalnızca place_id/day_index/order_index (TripStop'un
    kendi sütunları; id/trip_id restore edilirken YENİDEN üretilir, tıpkı
    apply_itinerary'nin zaten yaptığı sil-yeniden-ekle gibi). Ad/koordinat/
    şehir gibi görüntüleme alanları BURADA SAKLANMAZ — Place hâlâ tek
    kaynak, restore anında `Place`den TEKRAR okunur (Place silinirse o an
    fark edilir, bkz. undo_apply_history'nin invalid_places kontrolü).

    `previous_itinerary_id`: bu olaydan HEMEN ÖNCE `Trip.applied_itinerary_id`
    neyse o — geri alma bunu restore eder. `itinerary_id` ise bu olayın
    SONUCUNDA `Trip.applied_itinerary_id`nin ne olduğu (normal apply için
    uygulanan itinerary; undo için `previous_itinerary_id`nin DEVRİ). İkisi
    de `ondelete=SET NULL`: bu satırların kalıcılığı, işaret ettikleri
    itinerary'nin silinip silinmemesinden TAMAMEN bağımsız (bkz. Milestone
    19 "Delete Saved Itinerary" — bir itinerary silindiğinde bu geçmiş
    kayıtları asla kaybolmaz, yalnızca ilgili FK'ları NULL'a düşer).
    """
    __tablename__ = "trip_itinerary_apply_history"

    id                     = Column(Integer, primary_key=True, index=True)
    trip_id                = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    # Bu olayın SONUCUNDA aktif olan itinerary — normal apply'da uygulanan
    # itinerary'nin kendisi; undo'da geri yüklenen önceki provenance.
    itinerary_id           = Column(Integer, ForeignKey("trip_itineraries.id", ondelete="SET NULL"), nullable=True, index=True)
    # Bu olaydan HEMEN ÖNCE aktif olan itinerary — undo edilirse buraya dönülür.
    previous_itinerary_id  = Column(Integer, ForeignKey("trip_itineraries.id", ondelete="SET NULL"), nullable=True)
    # Bu olaydan HEMEN ÖNCEki TripStop anlık görüntüsü — [{"place_id","day_index","order_index"}, ...].
    # `TripStop` her zaman create_trip anında doldurulduğundan (bkz. o
    # metodun kendi davranışı) bu asla "gerçekten yok" olmaz — ilk apply'da
    # bile trip'in o ana kadarki (oluşturuluş/manuel) durak listesini taşır;
    # bu yüzden NULLABLE DEĞİL, sahte/boş bir "ilk apply" özel durumu YOK.
    previous_stops         = Column(JSON, nullable=False)
    # False: normal "Uygula". True: "Geri Al" — bkz. sınıf docstring'i.
    is_undo                = Column(Boolean, nullable=False, default=False)
    actor_user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    applied_at             = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_apply_history_trip_applied", "trip_id", "applied_at"),
    )
