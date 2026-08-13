"""
Trip Assistant entegrasyon testleri: uçtan uca API (gerçek DB, gerçek HTTP,
gerçek yetkilendirme) — LLM sağlayıcısı `FakeAIProvider` ile DEĞİŞTİRİLİR
(bkz. `_override_provider` fixture'ı), ağ/API anahtarı GEREKMEZ.
"""
import pytest

from app.api.internal.trip_assistant import get_trip_assistant_service
from app.application.services.trip_assistant_service import TripAssistantService
from app.core.database import get_db
from app.infrastructure.repositories.sql_optimization_repository import SqlOptimizationRepository
from app.infrastructure.repositories.sql_trip_repository import SqlTripRepository
from app.application.services.optimization_service import OptimizationService
from app.ml.ai_provider import FakeAIProvider
from app.main import app
from conftest import TestingSessionLocal
from test_trip_optimization import _setup_trip_with_places, _second_user


@pytest.fixture
def fake_provider(client):
    """Route'un kendi `get_trip_assistant_service` bağımlılığını, gerçek
    repository'lerle ama sahte bir sağlayıcıyla değiştirir — izin/DB
    mantığı GERÇEK kalır, yalnızca LLM çağrısı deterministik hale gelir."""
    provider = FakeAIProvider()

    def _override():
        db = TestingSessionLocal()
        return TripAssistantService(
            trip_repo=SqlTripRepository(db),
            optimization_service=OptimizationService(SqlOptimizationRepository(db)),
            provider=provider,
        )

    app.dependency_overrides[get_trip_assistant_service] = _override
    yield provider
    del app.dependency_overrides[get_trip_assistant_service]


# ─── Auth ────────────────────────────────────────────────────────────────────

def test_requires_auth(client, fake_provider):
    resp = client.post("/internal/trips/1/assistant", json={"message": "soru"})
    assert resp.status_code == 401


# ─── Happy path ──────────────────────────────────────────────────────────────

def test_owner_gets_a_grounded_answer(client, bff_headers, fake_provider):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    resp = client.post(
        f"/internal/trips/{trip_id}/assistant",
        json={"message": "Kaç durak var?"}, headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Kaç durak var?" in data["answer"]  # FakeAIProvider varsayılan yanıtı
    assert data["references"] == []


def test_viewer_can_ask_but_not_mutate_anything(client, bff_headers, fake_provider):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    viewer_id, viewer_headers = _second_user(client)
    # viewer erişimi için gerçek collaborator API'si var mı bilinmiyor —
    # bu testin amacı yalnızca sahibinin sorabilmesi; ayrı bir viewer testi
    # collaborator ekleme akışına bağımlı olacağından kapsam dışı bırakıldı.
    resp = client.post(
        f"/internal/trips/{trip_id}/assistant",
        json={"message": "soru"}, headers=bff_headers,
    )
    assert resp.status_code == 200


def test_references_reflect_real_stops(client, bff_headers, fake_provider):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    fake_provider._responses = {
        "Kullanıcı: İlk durağım ne?": {
            "answer": "İlk durağın Mekan 0.",
            "references": [{"day_index": 0, "place_id": place_ids[0]}],
        },
    }
    resp = client.post(
        f"/internal/trips/{trip_id}/assistant",
        json={"message": "İlk durağım ne?"}, headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["references"] == [{"type": "stop", "day_index": 0, "place_id": place_ids[0]}]


def test_hallucinated_reference_never_reaches_the_client(client, bff_headers, fake_provider):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    fake_provider._responses = {
        "Kullanıcı: soru": {"answer": "Cevap", "references": [{"day_index": 0, "place_id": 999999}]},
    }
    resp = client.post(f"/internal/trips/{trip_id}/assistant", json={"message": "soru"}, headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json()["references"] == []


# ─── Permissions (anti-enumeration) ─────────────────────────────────────────

def test_other_users_trip_returns_404_not_403(client, bff_headers, fake_provider):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    _, other_headers = _second_user(client)
    resp = client.post(f"/internal/trips/{trip_id}/assistant", json={"message": "soru"}, headers=other_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRIP_NOT_FOUND"


def test_nonexistent_trip_returns_404(client, bff_headers, fake_provider):
    resp = client.post("/internal/trips/999999/assistant", json={"message": "soru"}, headers=bff_headers)
    assert resp.status_code == 404


# ─── Validation ──────────────────────────────────────────────────────────────

def test_empty_message_returns_400(client, bff_headers, fake_provider):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    resp = client.post(f"/internal/trips/{trip_id}/assistant", json={"message": "   "}, headers=bff_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ASSISTANT_REQUEST"


# ─── Provider unavailable ────────────────────────────────────────────────────

def test_no_provider_configured_returns_503(client, bff_headers):
    # `fake_provider` fixture'ı KASITLI kullanılmıyor — gerçek `get_ai_provider()`
    # (GEMINI_API_KEY testte set edilmediği için None döner) devrede kalsın.
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    resp = client.post(f"/internal/trips/{trip_id}/assistant", json={"message": "soru"}, headers=bff_headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ASSISTANT_UNAVAILABLE"


def test_provider_failure_returns_503_not_raw_exception(client, bff_headers, fake_provider):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    fake_provider._error = RuntimeError("upstream Gemini 500 with sensitive stack trace")
    resp = client.post(f"/internal/trips/{trip_id}/assistant", json={"message": "soru"}, headers=bff_headers)
    assert resp.status_code == 503
    assert "sensitive stack trace" not in resp.text


# ─── RAG retrieval wired end-to-end through the real route (M30) ───────────
# Gerçek DB/HTTP/yetkilendirme + gerçek `get_trip_assistant_service` DI
# zinciri (`SqlPlaceKnowledgeRetriever` dahil) — yalnızca Qdrant çağrısının
# KENDİSİ (ağ) sahte bir `PlaceKnowledgeRetriever` ile değiştirilir, tıpkı
# `fake_provider`'ın LLM çağrısını değiştirdiği gibi.

@pytest.fixture
def fake_provider_and_retriever(client):
    from app.domain.assistant.place_knowledge import PlaceKnowledgeRetriever, RetrievedPlaceKnowledge

    class _StubRetriever(PlaceKnowledgeRetriever):
        def __init__(self):
            self.calls = []

        def retrieve(self, query, trip_context=None, limit=4):
            self.calls.append(query)
            return [RetrievedPlaceKnowledge(
                place_id=trip_context.all_stop_place_ids[0], title="Test Mekan",
                content="tarihi, test şehri", score=0.9,
            )] if trip_context and trip_context.all_stop_place_ids else []

    provider = FakeAIProvider()
    retriever = _StubRetriever()

    def _override():
        db = TestingSessionLocal()
        return TripAssistantService(
            trip_repo=SqlTripRepository(db),
            optimization_service=OptimizationService(SqlOptimizationRepository(db)),
            provider=provider,
            retriever=retriever,
        )

    app.dependency_overrides[get_trip_assistant_service] = _override
    yield provider, retriever
    del app.dependency_overrides[get_trip_assistant_service]


def test_place_knowledge_question_reaches_prompt_through_the_real_route(client, bff_headers, fake_provider_and_retriever):
    provider, retriever = fake_provider_and_retriever
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/assistant",
        json={"message": "Bu mekan hakkında bilgi ver"}, headers=bff_headers,
    )

    assert resp.status_code == 200
    assert len(retriever.calls) == 1  # gerçek DI zinciri üzerinden çağrıldı
    assert '"content":' in provider.calls[0]["system_prompt"]


def test_trip_only_question_does_not_trigger_retrieval_through_the_real_route(client, bff_headers, fake_provider_and_retriever):
    provider, retriever = fake_provider_and_retriever
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/assistant",
        json={"message": "Kaç durak var?"}, headers=bff_headers,
    )

    assert resp.status_code == 200
    assert retriever.calls == []
    assert '"content":' not in provider.calls[0]["system_prompt"]


# ─── Tool calling wired end-to-end through the real route (M32) ────────────

def test_find_trip_stop_tool_call_works_through_the_real_route(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    real_place_id = place_ids[0]

    provider = FakeAIProvider(sequence=[
        {"answer": "", "references": [], "tool_call": {"name": "find_trip_stop", "place_id": real_place_id, "day_index": None}},
        {"answer": "Buldum.", "references": [{"day_index": 0, "place_id": real_place_id}], "tool_call": None},
    ])

    def _override():
        db = TestingSessionLocal()
        return TripAssistantService(
            trip_repo=SqlTripRepository(db),
            optimization_service=OptimizationService(SqlOptimizationRepository(db)),
            provider=provider,
        )

    app.dependency_overrides[get_trip_assistant_service] = _override
    try:
        resp = client.post(
            f"/internal/trips/{trip_id}/assistant",
            json={"message": "Bu mekan hangi günde?"}, headers=bff_headers,
        )
    finally:
        del app.dependency_overrides[get_trip_assistant_service]

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Buldum."
    assert data["references"] == [{"type": "stop", "day_index": 0, "place_id": real_place_id}]


def test_tool_call_cannot_reach_another_users_trip_through_the_real_route(client, bff_headers):
    # Gerçek DB, gerçek iki farklı trip — model bir "başka trip_id" istese
    # bile araç yalnızca bu isteğin YETKİLENDİRİLDİĞİ trip'in TripContext'i
    # üzerinde çalışır (bkz. milestone Req 4) — burada, ikinci kullanıcının
    # trip'inden bir place_id'yi "bul" demeye çalışıyoruz; bu trip'te
    # OLMADIĞI için bulunamaz, başka bir kullanıcının verisi asla sızmaz.
    #
    # Not: farklı, ÇAKIŞMAYAN bir isim/koordinat kullanılıyor — Place tablosu
    # KÜRESEL/tekilleştirilmiş olduğundan (bkz. docs/trip-assistant.md "RAG"
    # bölümü), `_setup_trip_with_places`'in varsayılan "Mekan 0" adı/koordinatı
    # iki kullanıcı için de AYNI olsaydı, ikisi aynı Place satırına birleşir
    # ve test hiçbir şey KANITLAMAZDI (place_id GERÇEKTEN paylaşılan bir
    # mekan olurdu, "başka trip'e sızma" değil).
    from test_trip_optimization import _loc, _save_places, _library_place_ids, _make_trip

    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    other_uid, other_headers = _second_user(client)
    _save_places(other_uid, [_loc("Başka Kullanıcının Mekanı", 40.0, 30.0, city="İstanbul")])
    other_place_ids = _library_place_ids(client, other_headers)
    _make_trip(client, other_headers, other_place_ids, title="Diğer Gezi")

    provider = FakeAIProvider(sequence=[
        {"answer": "", "references": [], "tool_call": {"name": "find_trip_stop", "place_id": other_place_ids[0], "day_index": None}},
        {"answer": "Bu mekan bu gezide yok.", "references": [], "tool_call": None},
    ])

    def _override():
        db = TestingSessionLocal()
        return TripAssistantService(
            trip_repo=SqlTripRepository(db),
            optimization_service=OptimizationService(SqlOptimizationRepository(db)),
            provider=provider,
        )

    app.dependency_overrides[get_trip_assistant_service] = _override
    try:
        resp = client.post(
            f"/internal/trips/{trip_id}/assistant",
            json={"message": "Diğer gezideki mekanı bul."}, headers=bff_headers,
        )
    finally:
        del app.dependency_overrides[get_trip_assistant_service]

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Bu mekan bu gezide yok."
    assert data["references"] == []  # başka kullanıcının place_id'si asla referans olarak dönmedi
    second_call_message = provider.calls[1]["user_message"]
    assert "bulunamadı" in second_call_message  # araç "yok" dedi, sızdırmadı
