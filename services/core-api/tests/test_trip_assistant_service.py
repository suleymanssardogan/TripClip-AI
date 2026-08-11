"""
TripAssistantService birim testleri — DB/HTTP/LLM YOK. `AbstractTripRepository`
hafif bir stub'la, sağlayıcı `FakeAIProvider`'la değiştirilir. Uçtan uca
(gerçek DB + HTTP) senaryolar test_trip_assistant.py'de (route entegrasyonu).
"""
import pytest

from app.application.dto.assistant_dto import AssistantMessageDTO
from app.application.services.trip_assistant_service import TripAssistantService, MAX_MESSAGE_LENGTH
from app.core.exceptions import (
    AssistantUnavailableException,
    InvalidAssistantRequestException,
    TripNotFoundException,
)
from app.domain.repositories.trip_repository import AbstractTripRepository
from app.ml.ai_provider import AIProviderError, FakeAIProvider


class _StubTripRepo(AbstractTripRepository):
    """Yalnızca bu servisin kullandığı iki metodu uygular — geri kalanı
    kasıtlı `NotImplementedError`, yanlışlıkla çağrılırsa test hemen patlar."""

    def __init__(self, access="owner", trip=None):
        self._access = access
        self._trip = trip or _trip()

    def resolve_access(self, trip_id, user_id):
        return self._access

    def get_trip(self, trip_id, user_id):
        return None if self._access is None else self._trip

    def create_trip(self, *a, **kw): raise NotImplementedError
    def list_trips(self, *a, **kw): raise NotImplementedError
    def update_stop_order(self, *a, **kw): raise NotImplementedError
    def delete_trip(self, *a, **kw): raise NotImplementedError


class _StubOptimizationService:
    def __init__(self, itinerary_dto=None, exc=None):
        self._dto = itinerary_dto
        self._exc = exc

    def get_itinerary(self, itinerary_id, user_id):
        if self._exc:
            raise self._exc
        return self._dto


def _trip(**overrides):
    base = {
        "id": 2, "title": "Gaziantep Gezisi", "total_distance_km": 12.4,
        "created_at": "2026-08-08T10:00:00",
        "days": [[
            {"place_id": 25, "name": "Antep", "lat": 37.06, "lng": 37.38,
             "city": "Gaziantep", "category": "tarihi", "day_index": 0, "order_index": 0},
        ]],
        "stops_count": 1, "owner_id": 1, "your_role": "owner",
        "applied_itinerary_id": None, "itinerary_applied_at": None,
    }
    base.update(overrides)
    return base


_UNSET = object()


def _service(access="owner", trip=None, provider=_UNSET, optimization_service=None):
    return TripAssistantService(
        trip_repo=_StubTripRepo(access=access, trip=trip),
        optimization_service=optimization_service or _StubOptimizationService(),
        provider=FakeAIProvider() if provider is _UNSET else provider,
    )


# ─── Validation ──────────────────────────────────────────────────────────────

def test_empty_message_is_rejected():
    with pytest.raises(InvalidAssistantRequestException):
        _service().ask(trip_id=2, user_id=1, message="   ")


def test_overlong_message_is_rejected():
    with pytest.raises(InvalidAssistantRequestException):
        _service().ask(trip_id=2, user_id=1, message="a" * (MAX_MESSAGE_LENGTH + 1))


# ─── Permissions (anti-enumeration) ─────────────────────────────────────────

def test_no_access_raises_trip_not_found_not_permission_denied():
    # bkz. resolve_access None -> TripNotFoundException (404), var olan ama
    # erişimi olmayan bir trip'in VARLIĞI bile sızdırılmaz.
    with pytest.raises(TripNotFoundException):
        _service(access=None).ask(trip_id=2, user_id=1, message="Bugün nereye gideceğim?")


def test_viewer_can_ask_the_assistant():
    # Asistan salt-okunur bir özellik — GET benzeri erişim kuralı: owner/
    # editor/viewer hepsi sorabilir (bkz. diğer GET rotalarının AYNI kuralı).
    result = _service(access="viewer").ask(trip_id=2, user_id=1, message="Kaç durak var?")
    assert result.answer


# ─── Provider unavailable ────────────────────────────────────────────────────

def test_no_provider_configured_raises_assistant_unavailable():
    with pytest.raises(AssistantUnavailableException):
        _service(provider=None).ask(trip_id=2, user_id=1, message="soru")


def test_provider_error_is_converted_to_assistant_unavailable_never_leaks_raw_exception():
    provider = FakeAIProvider(error=RuntimeError("Gemini 503 upstream"))
    with pytest.raises(AssistantUnavailableException) as exc_info:
        _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")
    assert "Gemini" not in str(exc_info.value)  # ham provider hatası SIZMAZ


def test_empty_provider_answer_raises_assistant_unavailable():
    provider = FakeAIProvider(responses={"Kullanıcı: soru": {"answer": "", "references": []}})
    with pytest.raises(AssistantUnavailableException):
        _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")


# ─── Grounding / context ─────────────────────────────────────────────────────

def test_system_prompt_contains_the_actual_trip_data_not_generic_knowledge():
    provider = FakeAIProvider()
    _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")
    system_prompt = provider.calls[0]["system_prompt"]
    assert "Antep" in system_prompt
    assert "Gaziantep Gezisi" in system_prompt


def test_history_is_bounded_to_max_turns():
    provider = FakeAIProvider()
    long_history = [AssistantMessageDTO(role="user", content=f"soru {i}") for i in range(20)]
    _service(provider=provider).ask(trip_id=2, user_id=1, message="son soru", history=long_history)
    conversation = provider.calls[0]["user_message"]
    assert "soru 0" not in conversation  # en eskiler kırpıldı
    assert "soru 19" in conversation
    assert "son soru" in conversation


# ─── Reference validation — hallucinated references are dropped ────────────

def test_valid_reference_is_kept():
    provider = FakeAIProvider(responses={
        "Kullanıcı: soru": {"answer": "İlk durağın Antep.", "references": [{"day_index": 0, "place_id": 25}]},
    })
    result = _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")
    assert len(result.references) == 1
    assert result.references[0].place_id == 25


def test_hallucinated_reference_to_nonexistent_stop_is_silently_dropped():
    provider = FakeAIProvider(responses={
        "Kullanıcı: soru": {"answer": "Cevap", "references": [{"day_index": 0, "place_id": 9999}]},
    })
    result = _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")
    assert result.references == []


def test_malformed_reference_shape_does_not_crash():
    provider = FakeAIProvider(responses={
        "Kullanıcı: soru": {"answer": "Cevap", "references": [{"day_index": "not-an-int"}]},
    })
    result = _service(provider=provider).ask(trip_id=2, user_id=1, message="soru")
    assert result.references == []


# ─── Applied itinerary enrichment ───────────────────────────────────────────

def test_applied_itinerary_fetch_failure_falls_back_gracefully_not_crash():
    trip = _trip(applied_itinerary_id=4)
    provider = FakeAIProvider()
    opt_service = _StubOptimizationService(exc=RuntimeError("itinerary deleted"))
    result = _service(trip=trip, provider=provider, optimization_service=opt_service).ask(
        trip_id=2, user_id=1, message="Bugün nereye gideceğim?"
    )
    assert result.answer  # çökmedi, trip-only context ile devam etti
