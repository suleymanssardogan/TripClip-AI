from sqlalchemy import Column, Integer, Enum, ForeignKey, DateTime, Index, UniqueConstraint
from app.core.database import Base
from app.models.trip_share_enums import CollaboratorRole
from datetime import datetime


class TripCollaborator(Base):
    """
    Gerçek yetki verisi — her erişim kontrolü (bkz.
    SqlTripRepository.resolve_access) bu tabloyu sorgular, TripShare'i değil.
    Bir davet kabul edildiğinde tek bir satır oluşur; `share_id` hangi
    davetten geldiğini işaretler (denetim amaçlı, yetki kontrolünde
    kullanılmaz).

    (trip_id, user_id) tekil: aynı kullanıcı bir trip'e birden fazla rolle
    eklenemez — ikinci bir davet kabul edilirse mevcut satır güncellenir,
    yeni satır eklenmez (bkz. SqlSharingRepository.accept_by_token).
    """
    __tablename__ = "trip_collaborators"

    id        = Column(Integer, primary_key=True, index=True)
    trip_id   = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role      = Column(Enum(CollaboratorRole), nullable=False)
    share_id  = Column(Integer, ForeignKey("trip_shares.id"), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", name="uq_trip_collaborators_trip_user"),
        Index("ix_trip_collaborators_user", "user_id"),
    )
