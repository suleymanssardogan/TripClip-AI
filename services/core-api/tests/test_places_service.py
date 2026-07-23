"""
PlacesService — saf yardımcı fonksiyon testleri (Türkçe metin normalizasyonu,
mesafe hesabı, OSM kategori eşleme, OCR düzeltme). Nominatim/Overpass'a hiçbir
gerçek ağ isteği atılmaz.
"""
import pytest

from app.ml.places_service import PlacesService


@pytest.fixture
def service():
    return PlacesService()


# ─── tr_lower / ascii_fold ─────────────────────────────────────────────────────

def test_tr_lower_handles_turkish_i_correctly():
    # Python'un yerleşik str.lower() İ→i̇ (nokta + combining dot) üretir — YANLIŞ.
    assert PlacesService.tr_lower("İSTANBUL") == "istanbul"
    assert PlacesService.tr_lower("IŞIK") == "ışık"


def test_ascii_fold_strips_turkish_diacritics():
    # ascii_fold her yerde tr_lower()'dan SONRA çağrılır (bkz. places_service.py
    # satır 250/256) — yalnızca küçük harf varyantlarını katlar, büyük harfli
    # girdi (Ş, Ğ, Ü...) production akışında hiç oluşmaz.
    assert PlacesService.ascii_fold(PlacesService.tr_lower("Göynük Şelalesi")) == "goynuk selalesi"
    assert PlacesService.ascii_fold("çamlık") == "camlik"


# ─── _haversine_km / _within_city_area ────────────────────────────────────────

def test_haversine_km_zero_distance_for_same_point(service):
    assert service._haversine_km(36.9, 30.7, 36.9, 30.7) == pytest.approx(0, abs=0.01)


def test_haversine_km_known_distance_istanbul_ankara(service):
    # İstanbul ~ Ankara arası kabaca 350km (kuş uçuşu)
    km = service._haversine_km(41.0082, 28.9784, 39.9334, 32.8597)
    assert 300 < km < 400


def test_within_city_area_true_when_no_city_center(service):
    assert service._within_city_area({"location": {"lat": 0, "lng": 0}}, None) is True


def test_within_city_area_rejects_far_away_place(service):
    # Antalya merkez ~ İstanbul: ~450km, max_km=180 sınırını aşar
    antalya_center = (36.8969, 30.7133)
    istanbul_place = {"name": "Halk Plaj", "location": {"lat": 41.0082, "lng": 28.9784}}
    assert service._within_city_area(istanbul_place, antalya_center, max_km=180) is False


def test_within_city_area_accepts_nearby_place(service):
    antalya_center = (36.8969, 30.7133)
    kas_place = {"name": "Kaputaş Plajı", "location": {"lat": 36.1611, "lng": 29.6389}}
    assert service._within_city_area(kas_place, antalya_center, max_km=180) is True


# ─── _overpass_class ───────────────────────────────────────────────────────────

def test_overpass_class_priority_order(service):
    # amenity tag'i varsa diğerlerinden önce gelmeli (fonksiyondaki sıra)
    assert service._overpass_class({"amenity": "cafe", "tourism": "attraction"}) == "amenity"
    assert service._overpass_class({"tourism": "museum"}) == "tourism"
    assert service._overpass_class({"historic": "castle"}) == "historic"
    assert service._overpass_class({}) == "place"


# ─── _categorize ────────────────────────────────────────────────────────────

def test_categorize_known_mapping(service):
    assert service._categorize("amenity", "cafe") == "Kafe"
    assert service._categorize("historic", "castle") == "Kale"
    assert service._categorize("natural", "beach") == "Plaj"


def test_categorize_falls_back_to_class_level_default(service):
    # (osm_class, osm_type) çiftinin tam eşleşmesi yoksa class bazlı varsayılana düşmeli
    assert service._categorize("tourism", "some_unknown_subtype") == "Turistik Alan"
    assert service._categorize("totally_unknown_class", "x") == "Mekan"


# ─── _restore_ocr_turkish ───────────────────────────────────────────────────────

def test_restore_ocr_turkish_fixes_known_word():
    assert PlacesService._restore_ocr_turkish("goynuk merkez") == "Göynük merkez"


def test_restore_ocr_turkish_returns_none_when_nothing_changed():
    # Değişiklik yoksa None döner — çağıran taraf bunu "düzeltme gerekmedi" olarak yorumlar
    assert PlacesService._restore_ocr_turkish("Antalya") is None


# ─── _ocr_fallback_variants ─────────────────────────────────────────────────────

def test_ocr_fallback_variants_includes_trailing_char_removed(service):
    variants = service._ocr_fallback_variants("Kaputasl Plajl")
    assert "Kaputasl Plaj" in variants


def test_ocr_fallback_variants_includes_first_word_alone(service):
    variants = service._ocr_fallback_variants("Kaleici Antalya")
    assert "Kaleici" in variants


def test_ocr_fallback_variants_empty_for_single_short_word(service):
    # Tek kelime ve kısa → ne trailing-char ne first-word varyantı üretilebilir
    assert service._ocr_fallback_variants("Ev") == []
