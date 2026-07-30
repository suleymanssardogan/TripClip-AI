"""
GeminiService — JSON parse dayanıklılığı, frame örnekleme, idempotency cache testleri.
Gerçek Gemini API'ye hiçbir istek atılmaz (_call her zaman mock'lanır).
"""
from unittest import mock

import pytest

from app.ml.gemini_service import GeminiService


@pytest.fixture
def service():
    return GeminiService()


# ─── _parse_json ──────────────────────────────────────────────────────────────

def test_parse_json_plain(service):
    assert service._parse_json('{"locations": []}') == {"locations": []}


def test_parse_json_inside_markdown_fence(service):
    raw = '```json\n{"locations": [{"name": "Kaputaş"}]}\n```'
    assert service._parse_json(raw) == {"locations": [{"name": "Kaputaş"}]}


def test_parse_json_extracts_object_from_surrounding_text(service):
    raw = 'Here you go:\n{"locations": [{"name": "Antalya"}]}\nHope that helps!'
    assert service._parse_json(raw) == {"locations": [{"name": "Antalya"}]}


def test_parse_json_recovers_locations_array_from_truncated_response(service):
    # Gerçek dünyada Gemini yanıtı token limitine takılıp yarıda kesilebilir —
    # tam obje parse edilemez ama "locations" array'i regex ile kurtarılabilir.
    raw = '{"locations": [{"name": "Antalya", "lat": 36.9}], "sum'
    result = service._parse_json(raw)
    assert result == {"locations": [{"name": "Antalya", "lat": 36.9}]}


def test_parse_json_raises_on_unparseable_text(service):
    import json
    with pytest.raises(json.JSONDecodeError):
        service._parse_json("bu hiç JSON değil, sadece düz metin")


# ─── _sample_frames ───────────────────────────────────────────────────────────

def test_sample_frames_returns_all_when_under_limit(service):
    frames = [f"f{i}.jpg" for i in range(5)]
    assert service._sample_frames(frames, n=10) == frames


def test_sample_frames_caps_at_n_when_over_limit(service):
    frames = [f"f{i}.jpg" for i in range(100)]
    sampled = service._sample_frames(frames, n=10)
    assert len(sampled) == 10
    # Eşit aralıklı seçim: ilk frame dahil, sıra korunmalı
    assert sampled[0] == "f0.jpg"
    assert sampled == sorted(sampled, key=frames.index)


# ─── extract_locations — idempotency cache ────────────────────────────────────

def test_extract_locations_returns_cached_result_without_calling_api(service):
    cached = [{"name": "Cached Yer", "lat": None, "lng": None, "type": "place"}]
    with mock.patch.object(service, "_cache_get", return_value=cached), \
         mock.patch.object(service, "_call") as mock_call:
        result = service.extract_locations(frames=[], transcript="", video_id=42)

    assert result == cached
    mock_call.assert_not_called()


def test_extract_locations_filters_invalid_names_and_coerces_coords(service):
    raw_response = (
        '{"locations": ['
        '{"name": "Kaputaş Plajı", "lat": "36.19", "lng": "29.69", "type": "beach"}, '
        '{"name": "ab", "lat": null, "lng": null, "type": "place"}, '
        '{"name": "Bişirici Kebap", "lat": "bozuk", "lng": null, "type": "restaurant"}'
        ']}'
    )
    with mock.patch.object(service, "_call", return_value=raw_response), \
         mock.patch.object(service, "_cache_get", return_value=None), \
         mock.patch.object(service, "_cache_set") as mock_cache_set:
        result = service.extract_locations(frames=[], transcript="", video_id=1)

    names = [loc["name"] for loc in result]
    assert "Kaputaş Plajı" in names
    assert "Bişirici Kebap" in names
    assert "ab" not in names  # 2 karakter → 3-80 aralığı dışında, filtrelenmeli

    kaputas = next(loc for loc in result if loc["name"] == "Kaputaş Plajı")
    assert kaputas["lat"] == pytest.approx(36.19)  # string → float coerce edilmeli

    bisirici = next(loc for loc in result if loc["name"] == "Bişirici Kebap")
    assert bisirici["lat"] is None  # parse edilemeyen koordinat → None'a düşmeli, hata fırlatmamalı

    mock_cache_set.assert_called_once()


# ─── Ağ hatalarında sessizce boş dönmek yerine fırlatma ────────────────────────
#
# Kök neden (2026-07-25): Gemini'ye DNS çözümlemesi başarısız olduğunda
# extract_locations/generate_travel_tips hatayı yutup [] / {"tips": [], ...}
# döndürüyordu. video_processor._safe_run bunu "başarılı, 0 sonuç" ile ayırt
# edemiyor ve degradation raporu (dolayısıyla kullanıcıya gösterilen "kısmi
# sonuç" uyarısı) yanlış şekilde ✅ OK gösteriyordu. Servisler artık fırlatıyor;
# _safe_run bunu yakalayıp fallback_used=True olarak doğru işaretliyor.

def test_extract_locations_raises_on_network_error(service):
    with mock.patch.object(service, "_call", side_effect=ConnectionError("DNS çözümlenemedi")), \
         mock.patch.object(service, "_cache_get", return_value=None):
        with pytest.raises(ConnectionError):
            service.extract_locations(frames=[], transcript="", video_id=1)


def test_generate_travel_tips_raises_on_network_error(service):
    with mock.patch.object(service, "_call", side_effect=ConnectionError("DNS çözümlenemedi")), \
         mock.patch.object(service, "_cache_get", return_value=None):
        with pytest.raises(ConnectionError):
            service.generate_travel_tips(["Gaziantep"], video_id=1)
