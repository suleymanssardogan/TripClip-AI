"""Minimal destruction evidence, deliberately without user IDs or file paths."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer
from app.core.database import Base


class PrivacyErasureRecord(Base):
    __tablename__ = "privacy_erasure_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(40), nullable=False)
    category = Column(String(40), nullable=False)
    count = Column(Integer, nullable=False)
    performed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class PendingFileErasure(Base):
    __tablename__ = "pending_file_erasures"
    id = Column(Integer, primary_key=True)
    file_path = Column(String(2048), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
