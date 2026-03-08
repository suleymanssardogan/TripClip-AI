from sqlalchemy import Column,Integer,String,DateTime,JSON,ForeignKey,Boolean
from app.core.database import Base
from datetime import datetime

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer,primary_key=True,index=True)
    user_id = Column(Integer,ForeignKey("users.id"))
    video_id = Column(Integer,ForeignKey("videos.id"))
    title = Column(String,nullable=False)
    locations = Column(JSON)
    timeline = Column(JSON)
    budget = Column(JSON)
    is_public = Column(Boolean,default=False)
    created_at = Column(DateTime,default=datetime.utcnow)