from sqlalchemy import Column,Integer,String,DateTime
from app.core.database import Base
from datetime import datetime

class User(Base):
    __tablename__ ="users"

    id = Column(Integer,primary_key=True,index=True)
    email = Column(String,unique=True,index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    