"""
QdrantService — collection oluşturma, lokasyon ekleme ve benzerlik aramasının
Qdrant/embedding istemcilerine doğru argümanlarla çağrı yaptığını doğrular.

Gerçek Qdrant/SentenceTransformer'a hiç bağlanılmaz — self.client ve
self.model doğrudan mock'lanarak _load()'un lazy-connect'i atlanır.
"""
from unittest import mock

import pytest

from app.ml.qdrant_service import QdrantService


@pytest.fixture
def service():
    svc = QdrantService()
    svc.client = mock.MagicMock()
    svc.model = mock.MagicMock()
    svc.model.encode.return_value = mock.MagicMock(tolist=lambda: [0.1, 0.2, 0.3])
    return svc


def _fake_collections(names):
    collections = mock.MagicMock()
    collections.collections = [mock.MagicMock(name=n) for n in names]
    # mock.MagicMock(name=...) sets the mock's repr, not the .name attribute —
    # .name must be set explicitly for the code under test to read it correctly.
    for c, n in zip(collections.collections, names):
        c.name = n
    return collections


# ─── create_collection ────────────────────────────────────────────────────────

def test_create_collection_creates_when_missing(service):
    service.client.get_collections.return_value = _fake_collections([])

    service.create_collection()

    service.client.create_collection.assert_called_once()
    _, kwargs = service.client.create_collection.call_args
    assert kwargs["collection_name"] == "locations"


def test_create_collection_skips_when_already_exists(service):
    service.client.get_collections.return_value = _fake_collections(["locations"])

    service.create_collection()

    service.client.create_collection.assert_not_called()


# ─── add_locations ────────────────────────────────────────────────────────────

def test_add_locations_upserts_correct_point_count(service):
    service.client.get_collections.return_value = _fake_collections(["locations"])
    locations = [
        {
            "original_name": "Kaputaş Plajı",
            "place_data": {"address": "Kaş, Antalya", "location": {"lat": 36.22, "lng": 29.45}, "type": "beach"},
        },
        {
            "original_name": "Kaleiçi",
            "place_data": {"address": "Antalya", "location": {"lat": 36.88, "lng": 30.70}, "type": "museum"},
        },
    ]

    count = service.add_locations(locations)

    assert count == 2
    service.client.upsert.assert_called_once()
    _, kwargs = service.client.upsert.call_args
    assert kwargs["collection_name"] == "locations"
    assert len(kwargs["points"]) == 2


def test_add_locations_embeds_name_and_address(service):
    service.client.get_collections.return_value = _fake_collections(["locations"])
    locations = [{"original_name": "Gaziantep Kalesi", "place_data": {"address": "Gaziantep"}}]

    service.add_locations(locations)

    service.model.encode.assert_called_once_with("Gaziantep Kalesi Gaziantep")


def test_add_locations_payload_includes_coordinates(service):
    service.client.get_collections.return_value = _fake_collections(["locations"])
    locations = [{
        "original_name": "Kaleiçi",
        "place_data": {"address": "Antalya", "location": {"lat": 36.88, "lng": 30.70}, "type": "museum"},
    }]

    service.add_locations(locations)

    point = service.client.upsert.call_args.kwargs["points"][0]
    assert point.payload["lat"] == 36.88
    assert point.payload["lng"] == 30.70
    assert point.payload["type"] == "museum"


def test_add_locations_empty_list_upserts_nothing(service):
    service.client.get_collections.return_value = _fake_collections(["locations"])
    count = service.add_locations([])
    assert count == 0
    service.client.upsert.assert_called_once_with(collection_name="locations", points=[])


# ─── search_similar ───────────────────────────────────────────────────────────

def _fake_result(name, address, lat, lng, score):
    r = mock.MagicMock()
    r.payload = {"name": name, "address": address, "lat": lat, "lng": lng}
    r.score = score
    return r


def test_search_similar_maps_results_and_rounds_score(service):
    service.client.search.return_value = [
        _fake_result("Kaleiçi", "Antalya", 36.88, 30.70, 0.876543),
    ]

    results = service.search_similar("tarihi çarşı")

    assert len(results) == 1
    assert results[0]["name"] == "Kaleiçi"
    assert results[0]["score"] == 0.877


def test_search_similar_passes_query_vector_and_limit(service):
    service.client.search.return_value = []

    service.search_similar("sahil", limit=3)

    service.model.encode.assert_called_once_with("sahil")
    _, kwargs = service.client.search.call_args
    assert kwargs["collection_name"] == "locations"
    assert kwargs["limit"] == 3


def test_search_similar_empty_results(service):
    service.client.search.return_value = []
    assert service.search_similar("bulunamayan yer") == []
