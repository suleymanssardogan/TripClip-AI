"""Offline reviewed excerpts. No scraping, URL fetching, or generated facts."""
from datetime import datetime
import hashlib
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, HttpUrl, model_validator
from app.models.place import Place
from app.models.place_knowledge_document import PlaceKnowledgeDocument
from app.application.services.deferred_work import enqueue


class KnowledgeInput(BaseModel):
    place_id: int = Field(gt=0)
    source_url: HttpUrl = Field(max_length=2048)
    source_title: str = Field(min_length=3, max_length=300)
    content: str = Field(min_length=30, max_length=4000)
    language: str = Field(default="tr", min_length=2, max_length=10)
    observed_at: datetime
    expires_at: datetime
    reviewed: Literal[True]
    origin: Literal["official", "editorial"]

    @model_validator(mode="after")
    def valid_dates_and_source(self):
        # Store UTC-naive dates consistently with existing ORM models.
        from datetime import timezone
        for name in ("observed_at", "expires_at"):
            value = getattr(self, name)
            if value.tzinfo:
                setattr(self, name, value.astimezone(timezone.utc).replace(tzinfo=None))
        now = datetime.utcnow()
        if self.observed_at > now or self.expires_at <= now or self.expires_at <= self.observed_at:
            raise ValueError("Source dates must be observed in the past and valid in the future")
        if urlsplit(str(self.source_url)).username or urlsplit(str(self.source_url)).password:
            raise ValueError("Source URL must not contain credentials")
        return self


def ingest_documents(db, records):
    """Validate the complete batch first. Caller owns the atomic commit."""
    documents = [KnowledgeInput.model_validate(record) for record in records]
    ids = {d.place_id for d in documents}
    existing = {r[0] for r in db.query(Place.id).filter(Place.id.in_(ids)).all()}
    if ids != existing:
        raise ValueError("Unknown place_id in knowledge batch")
    # One source per place per batch avoids duplicate rows with autoflush off.
    keys = [(d.place_id, str(d.source_url)) for d in documents]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate source in knowledge batch")
    for source in documents:
        url = str(source.source_url)
        document = db.query(PlaceKnowledgeDocument).filter_by(place_id=source.place_id, source_url=url).first()
        if document is None:
            document = PlaceKnowledgeDocument(place_id=source.place_id, source_url=url)
            db.add(document)
        for field in ("source_title", "content", "language", "observed_at", "expires_at"):
            setattr(document, field, getattr(source, field))
        document.updated_at = datetime.utcnow()
        document.origin = source.origin
        document.content_hash = hashlib.sha256(source.content.encode("utf-8")).hexdigest()
    for place_id in ids:
        enqueue(db, "place_index", place_id)
    return len(documents)
