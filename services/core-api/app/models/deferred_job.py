"""Durable, transaction-bound work. Broker messages carry only the row ID."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Index, Integer, String
from app.core.database import Base


class DeferredJob(Base):
    __tablename__ = "deferred_jobs"
    id = Column(Integer, primary_key=True)
    kind = Column(String(32), nullable=False)
    entity_id = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    lease_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_error = Column(String(100), nullable=True)
    __table_args__ = (Index("ix_deferred_jobs_due", "status", "available_at"),)
