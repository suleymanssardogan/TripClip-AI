from sqlalchemy import Column, Integer, ForeignKey, Index
from app.core.database import Base


class TripStop(Base):
    """
    Bir Trip içindeki tek durak — Place'e referans verir, veriyi kopyalamaz
    (isim/koordinat Place'te tek bir yerde kalır, Video.deduplicated_locations'ın
    tekrar düştüğü kopyalama sorununu burada tekrarlamamak için).
    `day_index` gün gruplaması, `order_index` o gün içindeki sıradır — Video'nun
    stop_order'ındaki "gün başına id listesi" ile aynı semantik, normalize edilmiş hali.
    """
    __tablename__ = "trip_stops"

    id          = Column(Integer, primary_key=True, index=True)
    trip_id     = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id    = Column(Integer, ForeignKey("places.id"), nullable=False, index=True)
    day_index   = Column(Integer, nullable=False, default=0)
    order_index = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_trip_stops_trip_day_order", "trip_id", "day_index", "order_index"),
    )
