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
    cached = {"region": {"city": "Antalya", "country": "Türkiye", "country_code": "tr"},
              "locations": [{"name": "Cached Yer", "type": "place", "city": "Antalya"}]}
    with mock.patch.object(service, "_cache_get", return_value=cached), \
         mock.patch.object(service, "_call") as mock_call:
        result = service.extract_locations(frames=[], transcript="", video_id=42)

    assert result == cached
    mock_call.assert_not_called()


def test_extract_locations_parses_region_and_filters_invalid_names(service):
    raw_response = (
        '{"region": {"city": "Gaziantep", "country": "Türkiye", "country_code": "TR"}, '
        '"locations": ['
        '{"name": "Metanet Lokantası", "type": "restaurant", "city": "Gaziantep"}, '
        '{"name": "ab", "type": "place"}, '
        '{"name": "Elmacı Pazarı", "type": "market"}'
        ']}'
    )
    with mock.patch.object(service, "_call", return_value=raw_response), \
         mock.patch.object(service, "_cache_get", return_value=None), \
         mock.patch.object(service, "_cache_set") as mock_cache_set:
        result = service.extract_locations(frames=[], transcript="", video_id=1)

    names = [loc["name"] for loc in result["locations"]]
    assert "Metanet Lokantası" in names
    assert "Elmacı Pazarı" in names
    assert "ab" not in names  # 2 karakter → 3-80 aralığı dışında, filtrelenmeli

    assert result["region"]["city"] == "Gaziantep"
    assert result["region"]["country_code"] == "tr"   # normalize edilmeli

    # Şehri verilmeyen mekan None ile gelir — çağıran o zaman region.city'ye düşer.
    elmaci = next(l for l in result["locations"] if l["name"] == "Elmacı Pazarı")
    assert elmaci["city"] is None

    mock_cache_set.assert_called_once()


# ─── normalize_extraction ─────────────────────────────────────────────────────
#
# Gemini'nin koordinatları güvenilmezdi (Şanlıurfa ~79 km sapma, beş mekan tek
# nokta), o yüzden artık koordinat İSTEMİYORUZ. Model yine de gönderirse
# yutulmalı — konumu çözmek gazetteer'ın işi.

def test_normalize_extraction_drops_model_supplied_coordinates(service):
    result = service.normalize_extraction(
        {"locations": [{"name": "Balıklıgöl", "lat": 37.15, "lng": 38.79, "type": "lake"}]}
    )
    assert result["locations"] == [{"name": "Balıklıgöl", "type": "lake", "city": None}]


def test_normalize_extraction_accepts_bare_string_list(service):
    # _line_fallback (JSON parse kurtarma yolu) düz string listesi üretir.
    result = service.normalize_extraction(["Göbeklitepe", "ab", "Balıklıgöl"])
    assert [l["name"] for l in result["locations"]] == ["Göbeklitepe", "Balıklıgöl"]
    assert result["region"] == {"city": None, "country": None, "country_code": None}


def test_normalize_extraction_rejects_malformed_country_code(service):
    # Nominatim countrycodes yalnızca ISO alpha-2 kabul eder; "Türkiye" ya da
    # "TUR" gönderilirse arama sıfır sonuç döndürür — sessizce düşürülmeli.
    for bad in ("Türkiye", "TUR", "t1", ""):
        result = service.normalize_extraction({"region": {"country_code": bad}, "locations": []})
        assert result["region"]["country_code"] is None, bad


def test_normalize_extraction_handles_garbage_input(service):
    for junk in (None, "düz metin", 42, {"locations": "liste değil"}):
        result = service.normalize_extraction(junk)
        assert result == {"region": {"city": None, "country": None, "country_code": None},
                          "locations": []}


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
