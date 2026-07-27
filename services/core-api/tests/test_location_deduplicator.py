"""
LocationDeduplicator — mesafe hesabı, importance-öncelikli dedup, ve
get_location_summary şekli için testler.
"""
import pytest

from app.ml.location_deduplicator import LocationDeduplicator


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
