from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from app.core.database import Base
from datetime import datetime
import enum

class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, nullable=False)  # ← DEĞİŞTİ
    file_path = Column(String, nullable=False)
    status = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED)
    duration = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
