from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from app.core.database import Base


class TripItineraryStop(Base):
    """
    Bir TripItinerary içindeki tek durak. TripStop'a benzer şekilde Place'e
    referans verir, veriyi kopyalamaz. `place_id` nullable + ondelete=SET
    NULL: bir Place ileride silinebilir (bkz. Place.first_seen_video_id ile
    aynı gerekçe) — geçmiş bir itinerary kaydı bu durumda satırı kaybetmemeli,
    yalnızca hangi Place'e ait olduğu bilgisini kaybetmeli.
    """
    __tablename__ = "trip_itinerary_stops"

    id                            = Column(Integer, primary_key=True, index=True)
    itinerary_id                  = Column(Integer, ForeignKey("trip_itineraries.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id                      = Column(Integer, ForeignKey("places.id", ondelete="SET NULL"), nullable=True, index=True)
    day_index                     = Column(Integer, nullable=False)
    order_index                   = Column(Integer, nullable=False)
    arrival_time                  = Column(String, nullable=True)   # "HH:MM"
    departure_time                = Column(String, nullable=True)   # "HH:MM"
    visit_duration_minutes        = Column(Integer, nullable=False)
    travel_time_to_next_minutes   = Column(Float, nullable=True)
    travel_distance_to_next_km    = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_itinerary_stops_itinerary_day_order", "itinerary_id", "day_index", "order_index"),
    )
