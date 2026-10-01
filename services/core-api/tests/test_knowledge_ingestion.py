from datetime import datetime, timedelta
from unittest import mock
import pytest
from pydantic import ValidationError
from tests.conftest import TestingSessionLocal
from tests.test_place_knowledge_retriever import _make_place, _trip_context, ContextStop
from app.application.services.knowledge_ingestion import ingest_documents, KnowledgeInput
from app.infrastructure.repositories.sql_place_knowledge_retriever import SqlPlaceKnowledgeRetriever
from app.models.place_knowledge_document import PlaceKnowledgeDocument
from app.models.deferred_job import DeferredJob


@pytest.fixture(autouse=True)
def clean_knowledge_rows():
    # Existing place tests recreate IDs on SQLite without FK cascades.
    # Source rows must not leak into an unrelated later fixture's place.
    yield
    with TestingSessionLocal() as db:
        db.query(PlaceKnowledgeDocument).delete()
        db.commit()


def _input(place_id):
    now = datetime.utcnow()
    return {"place_id": place_id, "source_url": "https://example.org/museum",
            "source_title": "Reviewed test source", "content": "Bu test kaynağı müzenin arkeolojik eserleri hakkında açıklama içerir.",
            "observed_at": (now - timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "reviewed": True, "origin": "official"}


@pytest.mark.parametrize("changes", [{"reviewed": False}, {"origin": "generated"},
    {"source_url": "javascript:alert(1)"}, {"source_url": "https://user:secret@example.org/"},
    {"expires_at": "2020-01-01T00:00:00"}, {"observed_at": "2099-01-01T00:00:00"}])
def test_invalid_or_unreviewed_sources_rejected(changes):
    with pytest.raises(ValidationError):
        KnowledgeInput.model_validate({**_input(1), **changes})


def test_source_ingestion_is_idempotent_and_schedules_index():
    with TestingSessionLocal() as db:
        place = _make_place(db)
        row = _input(place.id)
        assert ingest_documents(db, [row]) == 1
        db.commit()
        row["content"] = "Güncellenmiş test kaynağı müzenin tarihi eserleri hakkında açıklama içerir."
        ingest_documents(db, [row])
        db.commit()
        assert db.query(PlaceKnowledgeDocument).filter_by(place_id=place.id).count() == 1
        assert db.query(DeferredJob).filter_by(kind="place_index", entity_id=place.id).count() >= 1


def test_only_unexpired_reviewed_content_reaches_retrieval():
    with TestingSessionLocal() as db:
        place = _make_place(db)
        row = _input(place.id)
        ingest_documents(db, [row])
        db.commit()
        qdrant = mock.Mock()
        qdrant.search_places.return_value = [{"place_id": place.id, "score": .9}]
        context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])
        retriever = SqlPlaceKnowledgeRetriever(db, qdrant=qdrant)
        result = retriever.retrieve("Müze hakkında bilgi", context)[0]
        assert result.content == row["content"]
        assert result.to_dict()["sources"][0]["url"] == row["source_url"]
        document = db.query(PlaceKnowledgeDocument).filter_by(place_id=place.id).one()
        document.expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
        result = retriever.retrieve("Müze hakkında bilgi", context)[0]
        assert "sources" not in result.to_dict()
        assert row["content"] not in result.content


def test_unknown_places_and_duplicate_sources_fail_before_writes():
    with TestingSessionLocal() as db:
        with pytest.raises(ValueError, match="Unknown place"):
            ingest_documents(db, [_input(999999)])
        place = _make_place(db)
        row = _input(place.id)
        with pytest.raises(ValueError, match="Duplicate source"):
            ingest_documents(db, [row, row])


def test_assistant_sources_are_copied_from_retrieval_not_generated_by_model():
    from tests.test_trip_assistant_service import _service, _StubRetriever
    from app.domain.assistant.place_knowledge import RetrievedPlaceKnowledge
    from app.ml.ai_provider import FakeAIProvider
    source = {"title": "Reviewed source", "url": "https://example.org/source",
              "observed_at": "2026-09-30", "expires_at": "2026-10-30"}
    retrieved = RetrievedPlaceKnowledge(25, "Müze", "Kaynak içeriği", .9, {"sources": [source]})
    provider = FakeAIProvider(sequence=[{"answer": "Cevap", "references": [], "sources": ["invented"]}])
    result = _service(provider=provider, retriever=_StubRetriever(results=[retrieved])).ask(
        trip_id=2, user_id=1, message="Müze hakkında bilgi ver")
    assert result.sources == [source]
