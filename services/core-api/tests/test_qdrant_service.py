"""
QdrantService — Place embed/anlamsal arama testleri.

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
    for c, n in zip(collections.collections, names):
        c.name = n
    return collections


# ─── upsert_place ─────────────────────────────────────────────────────────────

def test_upsert_place_creates_collection_when_missing(service):
    service.client.get_collections.return_value = _fake_collections([])

    service.upsert_place(1, "Kaputaş Plajı", city="Antalya", category="Plaj")

    service.client.create_collection.assert_called_once()
    _, kwargs = service.client.create_collection.call_args
    assert kwargs["collection_name"] == "places"


def test_upsert_place_skips_collection_creation_when_already_ready(service):
    service.client.get_collections.return_value = _fake_collections(["places"])

    service.upsert_place(1, "Kaputaş Plajı")
    service.upsert_place(2, "Kaleiçi")

    # İlk çağrı koleksiyonu kontrol eder, ikincisi _collection_ready flag'i
    # sayesinde tekrar get_collections çağırmamalı.
    assert service.client.get_collections.call_count == 1


def test_upsert_place_uses_place_id_as_point_id(service):
    service.client.get_collections.return_value = _fake_collections(["places"])

    service.upsert_place(42, "Kaleiçi", city="Antalya", category="Tarihi Alan")

    _, kwargs = service.client.upsert.call_args
    point = kwargs["points"][0]
    assert point.id == 42
    assert point.payload == {
        "place_id": 42, "name": "Kaleiçi", "city": "Antalya", "category": "Tarihi Alan",
    }


def test_upsert_place_embeds_name_city_category():
    svc = QdrantService()
    svc.client = mock.MagicMock()
    svc.model = mock.MagicMock()
    svc.model.encode.return_value = mock.MagicMock(tolist=lambda: [0.1])
    svc.client.get_collections.return_value = _fake_collections(["places"])

    svc.upsert_place(1, "Kaputaş Plajı", city="Antalya", category="Plaj")

    svc.model.encode.assert_called_once_with("Kaputaş Plajı, Antalya, Plaj")


def test_upsert_place_omits_missing_fields_from_embedding_text():
    svc = QdrantService()
    svc.client = mock.MagicMock()
    svc.model = mock.MagicMock()
    svc.model.encode.return_value = mock.MagicMock(tolist=lambda: [0.1])
    svc.client.get_collections.return_value = _fake_collections(["places"])

    svc.upsert_place(1, "Bilinmeyen Yer")

    svc.model.encode.assert_called_once_with("Bilinmeyen Yer")


def test_upsert_place_swallows_qdrant_errors(service):
    service.client.get_collections.side_effect = RuntimeError("connection refused")

    # Exception fırlatmamalı — best-effort.
    service.upsert_place(1, "Kaleiçi")


# ─── search_place_ids ─────────────────────────────────────────────────────────

def _fake_hit(place_id, score):
    r = mock.MagicMock()
    r.payload = {"place_id": place_id}
    r.score = score
    return r


def test_search_returns_empty_list_when_no_place_ids_given(service):
    assert service.search_place_ids("plaj", place_ids=[]) == []
    service.client.search.assert_not_called()


def test_search_filters_by_place_ids(service):
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = [_fake_hit(5, 0.9), _fake_hit(2, 0.7)]

    result = service.search_place_ids("sahil kenarı", place_ids=[5, 2, 9], limit=10)

    assert result == [5, 2]
    _, kwargs = service.client.search.call_args
    assert kwargs["collection_name"] == "places"
    assert kwargs["limit"] == 10
    qfilter = kwargs["query_filter"]
    assert qfilter.must[0].match.any == [5, 2, 9]


def test_search_returns_empty_list_on_qdrant_error(service):
    service.client.get_collections.side_effect = RuntimeError("unreachable")

    result = service.search_place_ids("plaj", place_ids=[1, 2])

    assert result == []


def test_search_returns_empty_list_when_no_hits(service):
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = []

    assert service.search_place_ids("bulunamayan yer", place_ids=[1]) == []


def test_search_forwards_a_bounded_timeout_to_qdrant_client(service):
    # M30 — Trip Assistant RAG'in tek bağlı (bounded) ağ çağrısı olması
    # gerektiği için eklendi; var olan search_place_ids çağrısı da (bu test
    # onun üzerinden kontrol ediyor) aynı sınırdan faydalanır.
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = []

    service.search_place_ids("plaj", place_ids=[1])

    _, kwargs = service.client.search.call_args
    assert isinstance(kwargs["timeout"], int) and kwargs["timeout"] > 0


# ─── search_places (M30 — Trip Assistant RAG) ───────────────────────────────

def test_search_places_returns_place_id_and_score(service):
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = [_fake_hit(5, 0.9), _fake_hit(2, 0.7)]

    result = service.search_places("Zeugma Müzesi hakkında", place_ids=[5, 2, 9], limit=4)

    assert result == [{"place_id": 5, "score": 0.9}, {"place_id": 2, "score": 0.7}]
    _, kwargs = service.client.search.call_args
    assert kwargs["limit"] == 4
    assert kwargs["query_filter"].must[0].match.any == [5, 2, 9]


def test_search_places_returns_empty_list_when_no_place_ids_given(service):
    assert service.search_places("plaj", place_ids=[]) == []
    service.client.search.assert_not_called()


def test_search_places_returns_empty_list_on_qdrant_error(service):
    service.client.get_collections.side_effect = RuntimeError("unreachable")

    assert service.search_places("plaj", place_ids=[1, 2]) == []


def test_search_places_returns_empty_list_when_no_hits(service):
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = []

    assert service.search_places("bulunamayan yer", place_ids=[1]) == []


def test_search_places_and_search_place_ids_reuse_the_same_qdrant_call(service):
    # Milestone Req 4/14 — iki ayrı Qdrant client/embedding çağrısı DEĞİL,
    # tek paylaşılan `_search` üzerinden.
    service.client.get_collections.return_value = _fake_collections(["places"])
    service.client.search.return_value = [_fake_hit(5, 0.9)]

    service.search_place_ids("plaj", place_ids=[5])
    service.search_places("plaj", place_ids=[5])

    assert service.model.encode.call_count == 2  # her çağrı kendi embedding'ini üretir
    assert service.client.search.call_count == 2
