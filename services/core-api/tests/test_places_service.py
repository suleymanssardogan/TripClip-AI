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


# ─── Bölge çözümleme (resolve_region) ─────────────────────────────────────────
#
# Bölge sınırı ARAMADAN ÖNCE çıkarılıyor. Eski sıralama — önce bölgesiz ara,
# sonra baskın ile göre düzelt — Gaziantep videosunda "Efendioğlu"nu Osmaniye'de
# bir eczaneye (100 km) bağlamış ve 180 km penceresine girdiği için kabul etmişti.

def test_bbox_from_nominatim_reorders_axes():
    # Nominatim ["lat_min","lat_max","lon_min","lon_max"] sırasıyla döner;
    # bizim tüm bbox tüketicilerimiz (viewbox, _within_bbox) lat/lon çiftlerini
    # (lat_min, lon_min, lat_max, lon_max) sırasında bekliyor.
    assert PlacesService._bbox_from_nominatim(["36.5", "37.5", "37.0", "38.0"]) == \
        (36.5, 37.0, 37.5, 38.0)


def test_bbox_from_nominatim_returns_none_on_malformed_input():
    for bad in (None, [], ["1", "2", "3"], ["a", "b", "c", "d"]):
        assert PlacesService._bbox_from_nominatim(bad) is None, bad


def test_within_bbox_true_when_no_bbox(service):
    assert service._within_bbox({"location": {"lat": 0, "lng": 0}}, None) is True


def test_within_bbox_rejects_point_outside(service):
    bbox = (36.5, 37.0, 37.5, 38.0)          # kabaca Gaziantep çevresi
    osmaniye = {"location": {"lat": 37.0813, "lng": 36.2626}}
    assert service._within_bbox(osmaniye, bbox) is False


def test_within_bbox_accepts_point_inside(service):
    bbox = (36.5, 37.0, 37.5, 38.0)
    metanet = {"location": {"lat": 37.0609, "lng": 37.3882}}
    assert service._within_bbox(metanet, bbox) is True


def test_resolve_region_pads_degenerate_point_bbox(service, monkeypatch):
    # Nominatim bir şehri NOKTA olarak döndürdüğünde boundingbox neredeyse
    # sıfırdır. Pay eklenmezse hiçbir mekan kutuya girmez ve bölge kısıtı
    # aramaların tamamını öldürür.
    monkeypatch.setattr(service, "search_place", lambda *a, **k: {
        "name": "Gaziantep",
        "location": {"lat": 37.0628, "lng": 37.3793},
        "boundingbox": ["37.0628", "37.0629", "37.3793", "37.3794"],
    })
    region = service.resolve_region(city="Gaziantep", country_code="tr")
    lat_min, lon_min, lat_max, lon_max = region["bbox"]
    assert lat_max - lat_min >= 2 * PlacesService.REGION_BBOX_MIN_HALF_DEG
    assert lon_max - lon_min >= 2 * PlacesService.REGION_BBOX_MIN_HALF_DEG
    assert region["center"] == (37.0628, 37.3793)


def test_resolve_region_keeps_wide_bbox_and_adds_margin(service, monkeypatch):
    # Gerçek bir il sınırı asgari kutudan genişse daraltılmamalı; POI'ler idari
    # sınırın hemen dışında kalabildiği için üstüne pay ekleniyor.
    monkeypatch.setattr(service, "search_place", lambda *a, **k: {
        "name": "Antalya",
        "location": {"lat": 36.9, "lng": 30.7},
        "boundingbox": ["36.0", "37.5", "29.3", "32.0"],
    })
    lat_min, lon_min, lat_max, lon_max = service.resolve_region(city="Antalya")["bbox"]
    pad = PlacesService.REGION_BBOX_PAD_DEG
    assert lat_min == pytest.approx(36.0 - pad)
    assert lon_max == pytest.approx(32.0 + pad)


def test_resolve_region_returns_none_when_unresolvable(service, monkeypatch):
    # Çözülemezse çağıran bölgesiz aramaya devam etmeli — çökmemeli.
    monkeypatch.setattr(service, "search_place", lambda *a, **k: None)
    assert service.resolve_region(city="Bilinmeyen Yer") is None
    assert service.resolve_region() is None   # sorgu boş


def test_resolve_region_appends_parent_context(service, monkeypatch):
    # "Kemer" ülke genelinde tekil değil (Antalya/Kemer ve Muğla/Seydikemer).
    # Üst bölge sorguya eklenmeli ki Nominatim doğru olanı öne alsın.
    seen = {}
    monkeypatch.setattr(service, "search_place",
                        lambda q, **k: seen.update(q=q, kw=k) or None)
    service.resolve_region(city="Kemer", country="Türkiye",
                           country_code="tr", parent="Antalya")
    assert seen["q"] == "Kemer, Antalya, Türkiye"
    assert seen["kw"]["prefer_area"] is True


def test_resolve_region_drops_parent_when_same_as_city(service, monkeypatch):
    # "Antalya, Antalya, Türkiye" anlamsız — üst bölge şehirle aynıysa düşmeli.
    seen = {}
    monkeypatch.setattr(service, "search_place",
                        lambda q, **k: seen.update(q=q) or None)
    service.resolve_region(city="Antalya", country="Türkiye", parent="antalya")
    assert seen["q"] == "Antalya, Türkiye"
