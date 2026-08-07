from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Index
from app.core.database import Base
from datetime import datetime


class TripItinerary(Base):
    """
    AI Trip Optimizer'ın bir Trip için ürettiği tek bir itinerary çalıştırması.

    Trip Builder'ın TripStop'unu KASITLI olarak mutasyona uğratmaz — bir
    itinerary, üretildiği o an için bir öneridir, Trip'in "kanonik" durağı
    değil (bkz. docs/trip-optimizer.md "Architecture: neden TripStop'a
    yazılmıyor"). Bu sayede aynı trip için birden çok itinerary geçmişte
    kalır, biri diğerini sessizce ezmez — optimizer'ı yeniden çalıştırmak
    hep güvenli bir "önizle" işlemidir.
    """
    __tablename__ = "trip_itineraries"

    id                          = Column(Integer, primary_key=True, index=True)
    trip_id                     = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_name                = Column(String, nullable=False)
    optimization_score           = Column(Float, nullable=False)
    total_distance_km            = Column(Float, nullable=False)
    total_travel_time_minutes    = Column(Float, nullable=False)
    # İstek parametreleri (place_ids, start_date, duration_days, saat tercihleri) —
    # tekrar üretilebilirlik/denetim için saklanır, iş mantığında okunmaz.
    params                        = Column(JSON, nullable=True)
    warnings                      = Column(JSON, nullable=False, default=list)
    created_at                    = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_trip_itineraries_trip_created", "trip_id", "created_at"),
    )
