"""
`SqlPlaceKnowledgeRetriever` birim testleri — gerçek Qdrant'a hiç
bağlanılmaz (`QdrantService` mock'lanır); Postgres tarafı gerçek (SQLite
in-memory, `client`/`db` fixture'ları — bkz. conftest.py) çünkü Place
kaydı gerçek bir model nesnesi olmalı.
"""
from unittest import mock

import pytest

from app.domain.assistant.context_builder import ContextDay, ContextStop, TripContext
from app.infrastructure.repositories.sql_place_knowledge_retriever import SqlPlaceKnowledgeRetriever
from app.models.place import Place


def _make_place(db, **overrides):
    base = dict(name="Zeugma Müzesi", name_key="zeugma muzesi", lat=37.05, lng=37.35,
                city="Gaziantep", address="Mozaik Cd. No:1", category="müze", save_count=0)
    base.update(overrides)
    place = Place(**base)
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


def _trip_context(stops=None, cities=None):
    stops = stops or []
    return TripContext(
        trip_id=2, title="Gaziantep Gezisi", today="2026-08-11",
        has_applied_itinerary=False, itinerary_applied_at=None,
        days=[ContextDay(day_index=0, date=None, stops=stops)] if stops else [],
    )


@pytest.fixture
def db_session():
    # Test DB'sinin KENDİSİ conftest'teki paylaşılan SQLite motoru — ayrı
    # bir engine açmaya gerek yok, `client` fixture'ı zaten Base.metadata'yı
    # oluşturuyor (bkz. conftest.py `setup_db`, autouse+session-scoped).
    from conftest import TestingSessionLocal
    db = TestingSessionLocal()
    yield db
    db.query(Place).delete()
    db.commit()
    db.close()


@pytest.fixture
def qdrant():
    return mock.MagicMock()


def test_retrieve_returns_matching_result(client, db_session, qdrant):
    place = _make_place(db_session)
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.87}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0, city="Gaziantep")])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("Zeugma Müzesi hakkında bilgi", trip_context=context, limit=4)

    assert len(results) == 1
    assert results[0].place_id == place.id
    assert results[0].title == "Zeugma Müzesi"
    assert results[0].score == 0.87
    assert "müze" in results[0].content
    assert "Gaziantep" in results[0].content


def test_retrieve_maps_metadata_correctly(client, db_session, qdrant):
    place = _make_place(db_session, category="tarihi", city="Gaziantep")
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.5}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("soru", trip_context=context)

    assert results[0].metadata == {"city": "Gaziantep", "category": "tarihi", "opening_hours": None}


# ─── opening_hours (M31 — a real, existing, previously-unexposed Place field) ─

def test_retrieve_includes_opening_hours_in_content_when_present(client, db_session, qdrant):
    place = _make_place(db_session, opening_hours="09:00-18:00")
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.6}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("soru", trip_context=context)

    assert "09:00-18:00" in results[0].content
    assert results[0].metadata["opening_hours"] == "09:00-18:00"


def test_retrieve_omits_opening_hours_cleanly_when_absent(client, db_session, qdrant):
    # Bugün prod'daki BÜYÜK ÇOĞUNLUK durum — hiçbir pipeline dolduruyor.
    place = _make_place(db_session, opening_hours=None)
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.6}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("soru", trip_context=context)

    assert "açılış saatleri" not in results[0].content
    assert results[0].metadata["opening_hours"] is None
    # Var olan alanlar (category/city/address) hâlâ SAĞLAM — opening_hours
    # eklenmesi diğer alanları BOZMADI.
    assert "müze" in results[0].content
    assert "Gaziantep" in results[0].content


def test_retrieve_still_bounds_content_length_with_opening_hours_present(client, db_session, qdrant):
    place = _make_place(db_session, category="a" * 500, city=None, address=None, opening_hours="09:00-18:00")
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.4}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("soru", trip_context=context)

    assert len(results[0].content) == SqlPlaceKnowledgeRetriever.MAX_CONTENT_LENGTH + 1
    assert results[0].content.endswith("…")


def test_retrieve_enforces_result_limit_passed_through(client, db_session, qdrant):
    place = _make_place(db_session)
    qdrant.search_places.return_value = []
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    retriever.retrieve("soru", trip_context=context, limit=2)

    _, kwargs = qdrant.search_places.call_args
    assert kwargs["limit"] == 2


def test_retrieve_bounds_content_length(client, db_session, qdrant):
    place = _make_place(db_session, category="a" * 500, city=None, address=None)
    qdrant.search_places.return_value = [{"place_id": place.id, "score": 0.4}]
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    results = retriever.retrieve("soru", trip_context=context)

    assert len(results[0].content) == SqlPlaceKnowledgeRetriever.MAX_CONTENT_LENGTH + 1  # + "…"
    assert results[0].content.endswith("…")


def test_retrieve_handles_no_hits_cleanly(client, db_session, qdrant):
    place = _make_place(db_session)
    qdrant.search_places.return_value = []
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    assert retriever.retrieve("soru", trip_context=context) == []


def test_retrieve_skips_search_entirely_without_trip_context(client, db_session, qdrant):
    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    assert retriever.retrieve("soru", trip_context=None) == []
    qdrant.search_places.assert_not_called()


def test_retrieve_ignores_qdrant_hit_for_a_deleted_place(client, db_session, qdrant):
    # Qdrant point'i var ama Postgres kaydı yok (silinmiş/tutarsız) —
    # halüsinasyon üretmeden sessizce atlanmalı.
    context = _trip_context(stops=[ContextStop(place_id=999, name="Hayalet Mekan", order_index=0)])
    qdrant.search_places.return_value = [{"place_id": 999, "score": 0.9}]

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    assert retriever.retrieve("soru", trip_context=context) == []


def test_retrieve_falls_back_cleanly_when_qdrant_raises(client, db_session, qdrant):
    place = _make_place(db_session)
    qdrant.search_places.side_effect = RuntimeError("Qdrant unreachable")
    context = _trip_context(stops=[ContextStop(place_id=place.id, name=place.name, order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    assert retriever.retrieve("soru", trip_context=context) == []


def test_search_text_includes_trip_stop_names_for_trip_aware_retrieval(client, db_session, qdrant):
    place = _make_place(db_session, name="Gaziantep Kalesi")
    qdrant.search_places.return_value = []
    context = _trip_context(stops=[ContextStop(place_id=place.id, name="Gaziantep Kalesi", order_index=0)])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    retriever.retrieve("Bunlardan hangisi Roma tarihi açısından önemli?", trip_context=context)

    search_text = qdrant.search_places.call_args[0][0]
    assert "Bunlardan hangisi Roma tarihi açısından önemli?" in search_text
    assert "Gaziantep Kalesi" in search_text


def test_candidate_pool_includes_other_places_in_same_city(client, db_session, qdrant):
    # Trip'te OLMAYAN, ama aynı şehirdeki bir mekan da aday havuzuna girmeli
    # (bkz. "yakın başka tarihi yerler" örneği) — trip'in KENDİ durağı 1,
    # aynı şehirdeki diğer mekan 2 numaralı yer.
    trip_place = _make_place(db_session, name="Zeugma Müzesi", city="Gaziantep")
    other_place = _make_place(db_session, name="Gaziantep Kalesi", name_key="gaziantep kalesi", city="Gaziantep")
    qdrant.search_places.return_value = []
    context = _trip_context(stops=[ContextStop(place_id=trip_place.id, name=trip_place.name, order_index=0, city="Gaziantep")])

    retriever = SqlPlaceKnowledgeRetriever(db_session, qdrant=qdrant)
    retriever.retrieve("yakın başka tarihi yerler", trip_context=context)

    candidate_ids = qdrant.search_places.call_args[0][1]
    assert trip_place.id in candidate_ids
    assert other_place.id in candidate_ids
