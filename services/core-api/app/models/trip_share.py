from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Index
from app.core.database import Base
from app.models.trip_share_enums import ShareStatus, CollaboratorRole
from datetime import datetime


class TripShare(Base):
    """
    Bir Trip için oluşturulmuş tek bir davet — yaşam döngüsü PENDING'ten
    başlar, ACCEPTED/DECLINED/EXPIRED/REVOKED'tan biriyle biter (geri dönüş
    yok, bkz. docs/trip-sharing.md "Invitation lifecycle").

    Gerçek gizli değer (paylaşılan URL'deki token) burada DEĞİL, ayrı
    ShareToken tablosunda — bu tablo bir sızıntıda tek başına hiçbir kimseye
    erişim vermez. `role`, kabul edildiğinde TripCollaborator'a kopyalanacak
    yetki seviyesidir.
    """
    __tablename__ = "trip_shares"

    id           = Column(Integer, primary_key=True, index=True)
    trip_id      = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by   = Column(Integer, ForeignKey("users.id"), nullable=False)
    role         = Column(Enum(CollaboratorRole), nullable=False)
    status       = Column(Enum(ShareStatus), nullable=False, default=ShareStatus.PENDING, index=True)
    accepted_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)
    # accepted/declined/expired/revoked anındaki zaman damgası — PENDING iken NULL.
    responded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_trip_shares_trip_status", "trip_id", "status"),
    )
