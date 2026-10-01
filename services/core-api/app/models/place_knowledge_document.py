from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class PlaceKnowledgeDocument(Base):
    """Operator-reviewed source excerpts; generated tips are never ingested."""
    __tablename__ = "place_knowledge_documents"
    id = Column(Integer, primary_key=True)
    place_id = Column(Integer, ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url = Column(String(2048), nullable=False)
    source_title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(10), nullable=False, default="tr")
    origin = Column(String(16), nullable=False)
    content_hash = Column(String(64), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("place_id", "source_url", name="uq_place_knowledge_source"),)
