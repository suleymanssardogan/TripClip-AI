from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey,Float,JSON
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
    filename = Column(String, nullable=False)  
    file_path = Column(String, nullable=False)
    status = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED)
    duration = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # AI Results
    processing_time = Column(Float, nullable=True)
    fps_processed = Column(Float , nullable=True)
    detections_count =Column(Integer,nullable=True)
    landmarks_count = Column(Integer,nullable=True)
    top_objects = Column(JSON,nullable=True)
    extracted_texts= Column(JSON,nullable=True)
    vision_landmarks = Column(JSON,nullable=True)
    transcription = Column(JSON,nullable=True)
    extracted_locations = Column(JSON,nullable=True)
    enriched_locations = Column(JSON,nullable=True)
    deduplicated_locations = Column(JSON, nullable=True)   
    location_summary = Column(JSON, nullable=True)         
    

    

 
