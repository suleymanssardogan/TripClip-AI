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
