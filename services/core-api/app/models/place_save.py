from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from app.core.database import Base
from datetime import datetime


class PlaceSave(Base):
    """
    Bir kullanıcının bir Place'i "kaydetmiş" olması — kütüphane ekranının
    veri kaynağı. Place global/paylaşılan bir kayıt (aynı mekanı birden
    çok kullanıcı çıkarabilir); PlaceSave kullanıcıya özel sahiplik satırı.

    video_id yalnızca köken bilgisi (hangi paylaşımdan geldiği) — video
    silinebildiği için nullable + ondelete=SET NULL; PlaceSave'in kendisi
    videodan bağımsız olarak kalıcı olmalı.
    """
    __tablename__ = "place_saves"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    saved_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Aynı kullanıcı aynı mekanı iki kez "kaydetmiş" görünmesin — iki
        # farklı Reel'de aynı yer çıkarsa save_count artmaz, tek satır kalır.
        UniqueConstraint("user_id", "place_id", name="uq_place_saves_user_place"),
        # Kütüphane ekranı: kullanıcının kayıtlarını tarihe göre listelemek için.
        Index("ix_place_saves_user_saved", "user_id", "saved_at"),
    )
