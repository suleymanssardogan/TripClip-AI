"""
LocationDeduplicator — mesafe hesabı, isim normalizasyonu, importance-öncelikli
dedup, ve get_location_summary şekli için testler.
"""
import pytest

from app.ml.location_deduplicator import LocationDeduplicator, normalize_place_name, place_name_stem


@pytest.fixture
def dedup():
    return LocationDeduplicator(distance_threshold_km=5.0)


def _loc(name: str, lat: float, lng: float, importance: float = 0.5) -> dict:
    return {
        "original_name": name,
        "place_data": {
            "name": f"{name} full",
            "type": "place",
            "importance": importance,
            "location": {"lat": lat, "lng": lng},
        },
    }


# ─── calculate_distance ──────────────────────────────────────────────────────

def test_calculate_distance_same_point_is_zero(dedup):
    assert dedup.calculate_distance(37.0, 37.0, 37.0, 37.0) == 0.0


def test_calculate_distance_far_apart_exceeds_threshold(dedup):
    dist = dedup.calculate_distance(37.06, 37.38, 61.13, 138.04)  # Gaziantep → Yakutya
    assert dist > 5.0


# ─── deduplicate_locations ────────────────────────────────────────────────────

def test_deduplicate_locations_empty_and_single_pass_through(dedup):
    assert dedup.deduplicate_locations([]) == []
    single = [_loc("Only", 37.0, 37.0)]
    assert dedup.deduplicate_locations(single) == single


def test_deduplicate_locations_removes_nearby_duplicate(dedup):
    # İki kayıt neredeyse aynı koordinatta (< 5km eşik) — biri elenmeli.
    locations = [
        _loc("A", 37.000, 37.000, importance=0.9),
        _loc("A-duplicate", 37.001, 37.001, importance=0.3),
    ]
    result = dedup.deduplicate_locations(locations)
    assert len(result) == 1


def test_deduplicate_locations_keeps_higher_importance_when_duplicate(dedup):
    locations = [
        _loc("LowImportance", 37.000, 37.000, importance=0.1),
        _loc("HighImportance", 37.001, 37.001, importance=0.9),
    ]
    result = dedup.deduplicate_locations(locations)
    assert len(result) == 1
    assert result[0]["original_name"] == "HighImportance"


def test_deduplicate_locations_keeps_distant_locations_separate(dedup):
    locations = [
        _loc("Gaziantep", 37.06, 37.38),
        _loc("Antalya", 36.88, 30.70),
    ]
    result = dedup.deduplicate_locations(locations)
    assert len(result) == 2


def test_deduplicate_locations_skips_entries_missing_coordinates(dedup):
    locations = [
        _loc("Valid", 37.0, 37.0),
        {"original_name": "NoCoords", "place_data": {"location": {}}},
    ]
    result = dedup.deduplicate_locations(locations)
    assert len(result) == 1
    assert result[0]["original_name"] == "Valid"


def test_deduplicate_locations_respects_custom_threshold():
    # 1km eşikle, 2km uzaklıktaki iki nokta duplicate SAYILMAMALI.
    tight_dedup = LocationDeduplicator(distance_threshold_km=1.0)
    locations = [
        _loc("A", 37.000, 37.000),
        _loc("B", 37.018, 37.000),  # ~2km kuzeyde
    ]
    result = tight_dedup.deduplicate_locations(locations)
    assert len(result) == 2


# ─── normalize_place_name ─────────────────────────────────────────────────────

def test_normalize_place_name_folds_turkish_characters():
    assert normalize_place_name("Kaş Halk Plajı") == normalize_place_name("Kas Halk Plajı")
    assert normalize_place_name("Düden Şelalesi") == normalize_place_name("Duden Şelalesi")
    assert normalize_place_name("Kaputaş Plajı") == normalize_place_name("Kaputas Plajı")


def test_normalize_place_name_handles_dotted_capital_i():
    # "İ".lower() birleşik nokta bırakır — normalizasyon bunu temizlemeli.
    assert normalize_place_name("İnönü Koyu") == normalize_place_name("inonu Koyu")


def test_normalize_place_name_strips_punctuation_and_whitespace():
    assert normalize_place_name("  Kaleiçi,  Antalya ") == "kaleici antalya"


def test_normalize_place_name_empty_input():
    assert normalize_place_name(None) == ""
    assert normalize_place_name("") == ""


def test_normalize_place_name_keeps_distinct_names_distinct():
    assert normalize_place_name("Kaş Plajı") != normalize_place_name("Kaş Halk Plajı")


# ─── isim tabanlı dedup ───────────────────────────────────────────────────────

def test_deduplicate_merges_same_name_despite_coordinate_drift():
    # Gerçek vaka: aynı plaj hem Gemini hem Nominatim'den gelmiş, isim Türkçe
    # karakterde ayrışmış ve koordinat ~200m kaymış. 1m eşikle mesafe kontrolü
    # bunu yakalayamaz — isim eşleşmesi yakalamalı.
    tight_dedup = LocationDeduplicator(distance_threshold_km=0.001)
    locations = [
        _loc("Kaş Halk Plajı", 36.1980, 29.6390, importance=0.0),
        _loc("Kas Halk Plajı", 36.1998, 29.6402, importance=0.4),
    ]
    result = tight_dedup.deduplicate_locations(locations)

    assert len(result) == 1
    # importance'ı yüksek olan (geocode edilmiş) kayıt kalmalı.
    assert result[0]["original_name"] == "Kas Halk Plajı"


def test_deduplicate_merges_exact_duplicate_names():
    tight_dedup = LocationDeduplicator(distance_threshold_km=0.001)
    locations = [
        _loc("Manavgat Şelalesi", 36.7880, 31.4430, importance=0.5),
        _loc("Manavgat Şelalesi", 36.7885, 31.4441, importance=0.2),
    ]
    assert len(tight_dedup.deduplicate_locations(locations)) == 1


def test_deduplicate_keeps_different_names_at_distinct_coordinates():
    tight_dedup = LocationDeduplicator(distance_threshold_km=0.001)
    locations = [
        _loc("Kaleiçi", 36.8841, 30.7079),
        _loc("Mermerli Plaj", 36.8852, 30.7050),
    ]
    assert len(tight_dedup.deduplicate_locations(locations)) == 2


def test_deduplicate_falls_back_to_distance_when_name_missing():
    tight_dedup = LocationDeduplicator(distance_threshold_km=5.0)
    locations = [
        {"place_data": {"importance": 0.9, "location": {"lat": 37.000, "lng": 37.000}}},
        {"place_data": {"importance": 0.1, "location": {"lat": 37.001, "lng": 37.001}}},
    ]
    assert len(tight_dedup.deduplicate_locations(locations)) == 1


# ─── get_location_summary ─────────────────────────────────────────────────────

def test_get_location_summary_shape(dedup):
    locations = [_loc("Kaleiçi", 36.88, 30.70, importance=0.4)]
    summary = dedup.get_location_summary(locations)

    assert summary["total_locations"] == 1
    entry = summary["locations"][0]
    assert entry["name"] == "Kaleiçi"
    assert entry["coordinates"] == {"lat": 36.88, "lng": 30.70}
    assert entry["importance"] == 0.4


def test_get_location_summary_reflects_deduplication(dedup):
    locations = [
        _loc("A", 37.000, 37.000, importance=0.9),
        _loc("A-duplicate", 37.001, 37.001, importance=0.3),
    ]
    summary = dedup.get_location_summary(locations)
    assert summary["total_locations"] == 1


# ── Gemini kaynaklı kayıtlarda mesafe kontrolü uygulanmaz ────────────────────

def _gemini_loc(name, lat, lng, source="gemini_coords"):
    return {
        "original_name": name,
        "place_data": {"location": {"lat": lat, "lng": lng},
                       "importance": 0.15, "source": source},
    }


def test_gemini_ayni_koordinatta_farkli_isimler_korunur():
    """Güllüoğlu, Elmacı Pazarı'nın İÇİNDE — aynı nokta, ayrı durak."""
    locs = [
        _gemini_loc("Elmacı Pazarı", 37.0640, 37.3800),
        _gemini_loc("Güllüoğlu Baklava", 37.0640, 37.3800),
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert {r["original_name"] for r in result} == {"Elmacı Pazarı", "Güllüoğlu Baklava"}


def test_gemini_sehir_merkezi_fallbacki_mekanlari_yutmaz():
    """Gemini bilmediği mekanlara şehir koordinatını verince hepsi kaybolmamalı."""
    locs = [
        _gemini_loc("Urfa", 37.1597, 37.9008),
        _gemini_loc("Ciğerci Aziz Usta", 37.1597, 37.9008),
        _gemini_loc("Safi Künefe", 37.1597, 37.9008),
        _gemini_loc("Gümrük Hanı", 37.1597, 37.9008),
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 4


def test_gemini_ayni_isim_yine_birlesir():
    """Mesafe muafiyeti ad bazlı dedup'ı devre dışı bırakmamalı."""
    locs = [
        _gemini_loc("Balıklıgöl", 37.1597, 37.9008),
        {"original_name": "balikligol",
         "place_data": {"location": {"lat": 37.1477, "lng": 38.7846}, "importance": 0.25}},
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 1
    # İyi geocode edilmiş olan (yüksek importance) kalmalı
    assert result[0]["original_name"] == "balikligol"


def test_nominatim_kayitlarinda_mesafe_dedupu_korunur():
    """Muafiyet yalnızca gemini_* kaynaklı kayıtlar için."""
    locs = [
        {"original_name": "Kaleiçi",
         "place_data": {"location": {"lat": 36.8841, "lng": 30.7079}, "importance": 0.5}},
        {"original_name": "Kaleici Marina",
         "place_data": {"location": {"lat": 36.8841, "lng": 30.7079}, "importance": 0.4}},
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 1


# ── Türkçe iyelik eki: kök eşleşmesi + yakınlık ──────────────────────────────

def test_stem_iyelik_ekini_dusurur():
    assert place_name_stem("Mermerli Plajı") == place_name_stem("Mermerli Plaj")
    assert place_name_stem("Elmacı Pazarı")  == "elmaci pazar"
    assert place_name_stem("Bakırcılar Çarşısı") == "bakircilar carsi"


def test_stem_kisa_adlara_dokunmaz():
    """'Kaş'taki sesli harf ek değil kökün parçası."""
    assert place_name_stem("Kaş") == "kas"
    assert place_name_stem("Urfa") == "urfa"
    assert place_name_stem("Patara") == "patara"


def test_mermerli_plaj_ikilisi_birlesir():
    locs = [
        _gemini_loc("Mermerli Plajı", 36.8830, 30.7060),
        _gemini_loc("Mermerli Plaj",  36.8832, 30.7029),
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 1


def test_ayni_kok_uzaktaysa_birlesmez():
    """Farklı ilçelerdeki aynı isimli mekanlar ayrı kalmalı."""
    locs = [
        _gemini_loc("Merkez Plajı", 36.8830, 30.7060),
        _gemini_loc("Merkez Plaj",  36.2000, 29.6380),   # ~120 km
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 2


def test_ic_ice_mekanlar_kok_farkliysa_korunur():
    """Güllüoğlu/Elmacı aynı noktada ama kökleri farklı — ikisi de kalmalı."""
    locs = [
        _gemini_loc("Elmacı Pazarı", 37.0640, 37.3800),
        _gemini_loc("Güllüoğlu Baklava", 37.0640, 37.3800),
    ]
    result = LocationDeduplicator(distance_threshold_km=0.001).deduplicate_locations(locs)
    assert len(result) == 2
