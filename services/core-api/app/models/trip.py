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

    __table_args__ = (
        Index("ix_trips_user_created", "user_id", "created_at"),
    )
