from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index
from app.core.database import Base
from datetime import datetime


class Trip(Base):
    """
    Kullanıcının Library'den seçtiği bir mekan alt kümesinden oluşturduğu,
    TSP ile rotalanmış gezi. Video'nun aksine tek bir videoya değil, birden
    çok videodan gelmiş olabilecek Place'lere referans verir (bkz. TripStop) —
    goal.md Phase 7 "Trip Builder" ekranının backend'i.
    """
    __tablename__ = "trips"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title             = Column(String, nullable=False)
    total_distance_km = Column(Float, nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, index=True)

    # Hangi TripItinerary'nin en son uygulandığını bilmek için — bkz.
    # docs/trip-optimizer.md "Apply semantics". Bilinçli olarak TripStop'a
    # DEĞİL Trip'e eklendi: her apply zaten TÜM TripStop'ları değiştiriyor,
    # bu yüzden durak-başına köken bilgisinin hiçbir faydası yok, yalnızca
    # optimizer domain'ine gereksiz bir bağımlılık eklerdi. ON DELETE SET
    # NULL: itinerary ileride silinebilir bir özellik kazanırsa Trip bundan
    # etkilenmemeli, yalnızca "son uygulanan" işaretçisini kaybetmeli.
    # use_alter=True: trips ↔ trip_itineraries dairesel bir FK ilişkisi
    # (trip_itineraries.trip_id zaten trips'e işaret ediyor) — bu olmadan
    # SQLAlchemy create_all/drop_all için güvenli bir tablo sırası
    # bulamıyor ("unresolvable foreign key dependency" uyarısı verip
    # yine de devam ediyor). use_alter, bu FK'nin ayrı bir ALTER
    # ifadesiyle kurulup kaldırılabileceğini belirtir, döngüyü çözer.
    applied_itinerary_id = Column(
        Integer,
        ForeignKey("trip_itineraries.id", ondelete="SET NULL", use_alter=True, name="fk_trips_applied_itinerary_id"),
        nullable=True,
    )
    itinerary_applied_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_trips_user_created", "user_id", "created_at"),
    )
