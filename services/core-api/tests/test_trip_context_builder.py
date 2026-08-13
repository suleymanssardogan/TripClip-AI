"""
TripContextBuilder birim testleri — DB/HTTP/LLM yok, yalnızca saf birleştirme
mantığı. `TripAssistantService`'in entegrasyon testleri
test_trip_assistant.py'de.
"""
from datetime import date

from app.domain.assistant.context_builder import build_trip_context


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


def _itinerary(**overrides):
    base = {
        "id": 4, "trip_id": 2, "strategy_name": "greedy_distance",
        "optimization_score": 87.5, "total_distance_km": 12.4, "total_travel_time_minutes": 29.8,
        "warnings": [], "created_at": "2026-08-08T10:00:00",
        "days": [{
            "day_index": 0, "date": "2026-08-08",
            "stops": [{
                "place_id": 25, "name": "Antep", "lat": 37.06, "lng": 37.38,
                "day_index": 0, "order_index": 0,
                "arrival_time": "09:00", "departure_time": "10:00",
                "visit_duration_minutes": 60,
                "travel_time_to_next_minutes": None, "travel_distance_to_next_km": None,
            }],
        }],
    }
    base.update(overrides)
    return base


# ─── No applied itinerary: falls back to the trip's own plain stop list ────

def test_no_itinerary_uses_trip_days_with_no_schedule():
    ctx = build_trip_context(_trip(), itinerary=None, today=date(2026, 8, 8))

    assert ctx.has_applied_itinerary is False
    assert len(ctx.days) == 1
    stop = ctx.days[0].stops[0]
    assert stop.name == "Antep"
    assert stop.city == "Gaziantep"
    assert stop.arrival_time is None  # trip_stops taşımıyor — UYDURULMADI
    assert ctx.today == "2026-08-08"


def test_empty_day_arrays_are_skipped_not_crashed():
    ctx = build_trip_context(_trip(days=[[], []]), itinerary=None, today=date(2026, 8, 8))
    assert ctx.days == []
    assert ctx.total_stops == 0


# ─── Applied itinerary: real schedule, city/category backfilled from trip ──

def test_applied_itinerary_provides_real_schedule():
    ctx = build_trip_context(_trip(applied_itinerary_id=4), itinerary=_itinerary(), today=date(2026, 8, 8))

    assert ctx.has_applied_itinerary is True
    stop = ctx.days[0].stops[0]
    assert stop.arrival_time == "09:00"
    assert stop.departure_time == "10:00"
    assert stop.visit_duration_minutes == 60
    assert ctx.days[0].date == "2026-08-08"


def test_applied_itinerary_backfills_city_and_category_from_trip_without_a_new_query():
    # ItineraryStop'ta city/category YOK — context builder bunları trip'in
    # KENDİ zaten-elde-olan verisinden place_id eşleşmesiyle tamamlıyor,
    # yeni bir DB sorgusu YOK.
    ctx = build_trip_context(_trip(applied_itinerary_id=4), itinerary=_itinerary(), today=date(2026, 8, 8))
    stop = ctx.days[0].stops[0]
    assert stop.city == "Gaziantep"
    assert stop.category == "tarihi"


def test_deleted_place_in_itinerary_is_skipped_not_crashed():
    # ItineraryStop.place_id nullable — mekan Library'den silinmişse.
    itinerary = _itinerary()
    itinerary["days"][0]["stops"].append({
        "place_id": None, "name": "Silinmiş Mekan", "lat": None, "lng": None,
        "day_index": 0, "order_index": 1, "arrival_time": "10:05", "departure_time": "10:35",
        "visit_duration_minutes": 30, "travel_time_to_next_minutes": None, "travel_distance_to_next_km": None,
    })
    ctx = build_trip_context(_trip(applied_itinerary_id=4), itinerary=itinerary, today=date(2026, 8, 8))
    assert len(ctx.days[0].stops) == 1
    assert ctx.days[0].stops[0].name == "Antep"


# ─── Missing coordinates handled gracefully, never fabricated ──────────────

def test_missing_coordinates_marked_explicitly_not_omitted_silently():
    trip = _trip(days=[[
        {"place_id": 1, "name": "Konumsuz", "lat": None, "lng": None,
         "city": None, "category": None, "day_index": 0, "order_index": 0},
    ]])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    stop_dict = ctx.days[0].stops[0].to_dict()
    assert stop_dict["has_location"] is False


# ─── Multi-day: day boundaries and stop order preserved ────────────────────

def test_multi_day_preserves_day_boundaries_and_stop_order():
    trip = _trip(days=[
        [{"place_id": 1, "name": "A", "lat": 1, "lng": 1, "city": None, "category": None, "day_index": 0, "order_index": 0}],
        [
            {"place_id": 3, "name": "C", "lat": 3, "lng": 3, "city": None, "category": None, "day_index": 1, "order_index": 1},
            {"place_id": 2, "name": "B", "lat": 2, "lng": 2, "city": None, "category": None, "day_index": 1, "order_index": 0},
        ],
    ])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))

    assert [d.day_index for d in ctx.days] == [0, 1]
    assert [s.name for s in ctx.days[1].stops] == ["C", "B"]  # sıra korunur, yeniden sıralanmaz


# ─── to_dict / find_stop — used by the prompt and reference validation ─────

def test_to_dict_is_json_ready_and_avoids_duplicated_top_level_fields():
    ctx = build_trip_context(_trip(), itinerary=None, today=date(2026, 8, 8))
    d = ctx.to_dict()
    assert d["trip_id"] == 2
    assert d["total_stops"] == 1
    assert d["total_days"] == 1
    assert isinstance(d["days"], list)


def test_find_stop_locates_by_day_index_and_place_id_not_array_position():
    trip = _trip(days=[[
        {"place_id": 99, "name": "X", "lat": 1, "lng": 1, "city": None, "category": None, "day_index": 0, "order_index": 5},
    ]])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    assert ctx.find_stop(day_index=0, place_id=99) is not None
    assert ctx.find_stop(day_index=0, place_id=1) is None
    assert ctx.find_stop(day_index=1, place_id=99) is None


# ─── all_stop_place_ids / all_cities — used by M30 RAG retrieval ───────────

def test_all_stop_place_ids_collects_ids_across_all_days():
    trip = _trip(days=[
        [{"place_id": 1, "name": "A", "lat": 1, "lng": 1, "city": None, "category": None, "day_index": 0, "order_index": 0}],
        [{"place_id": 2, "name": "B", "lat": 2, "lng": 2, "city": None, "category": None, "day_index": 1, "order_index": 0}],
    ])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    assert ctx.all_stop_place_ids == [1, 2]


def test_all_cities_deduplicates_and_preserves_order():
    trip = _trip(days=[[
        {"place_id": 1, "name": "A", "lat": 1, "lng": 1, "city": "Gaziantep", "category": None, "day_index": 0, "order_index": 0},
        {"place_id": 2, "name": "B", "lat": 2, "lng": 2, "city": "Antalya", "category": None, "day_index": 0, "order_index": 1},
        {"place_id": 3, "name": "C", "lat": 3, "lng": 3, "city": "Gaziantep", "category": None, "day_index": 0, "order_index": 2},
    ]])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    assert ctx.all_cities == ["Gaziantep", "Antalya"]


def test_all_cities_skips_missing_city():
    trip = _trip(days=[[
        {"place_id": 1, "name": "A", "lat": 1, "lng": 1, "city": None, "category": None, "day_index": 0, "order_index": 0},
    ]])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    assert ctx.all_cities == []


def test_all_stop_place_ids_empty_for_trip_with_no_stops():
    trip = _trip(days=[])
    ctx = build_trip_context(trip, itinerary=None, today=date(2026, 8, 8))
    assert ctx.all_stop_place_ids == []
    assert ctx.all_cities == []
