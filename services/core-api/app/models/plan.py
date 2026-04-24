from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean, Index
from app.core.database import Base
from datetime import datetime

class Plan(Base):
    __tablename__ = "plans"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), index=True)
    video_id   = Column(Integer, ForeignKey("videos.id"), index=True)
    title      = Column(String, nullable=False)
    locations  = Column(JSON)
    timeline   = Column(JSON)
    budget     = Column(JSON)
    is_public  = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Kullanıcının planlarını tarihe göre listelemek için
        Index("ix_plans_user_created", "user_id", "created_at"),
        # Public plan keşif feed'i
        Index("ix_plans_public_created", "is_public", "created_at"),
    )