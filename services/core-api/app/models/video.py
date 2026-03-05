from sqlalchemy import Column,Integer,String,DateTime,Enum
from app.core.database import Base
from datetime import datetime
import enum

class VideoStatus(str,enum.Enum):
    UPLOADED ="uploaded"
    PROCESSING ="processing"
    COMPLETED ="completed"
    FAILED ="failed"

class Video(Base):
    __tablename__="videos"

    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer)
    file_name = Column(String)
    file_path = Column(String)
    status = Column(Enum(VideoStatus),default=VideoStatus.UPLOADED)
    created_at = Column(DateTime,default=datetime.utcnow)

    