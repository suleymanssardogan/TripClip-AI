"""Minimal encrypted revocation outbox; deliberately no deleted-user foreign key."""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime
from app.core.database import Base


class AppleRevocation(Base):
    __tablename__ = "apple_revocations"
    id = Column(Integer, primary_key=True)
    encrypted_token = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
