"""
GreedyDistanceStrategy birim testleri — DB/HTTP yok, yalnızca strateji.
Servis/repository katmanı test_trip_optimization.py'de (entegrasyon).
"""
from app.domain.optimization.models import PlaceInput, OptimizationConstraints
from app.infrastructure.optimization.greedy_distance_strategy import GreedyDistanceStrategy


def _place(place_id, name, lat, lng, category=None, opening_hours=None) -> PlaceInput:
    return PlaceInput(place_id=place_id, name=name, lat=lat, lng=lng, category=category, opening_hours=opening_hours)


def _run(places, **overrides):
    constraints = OptimizationConstraints(**overrides)
    return GreedyDistanceStrategy().optimize(places, constraints)


# ─── Edge case: empty trip ──────────────────────────────────────────────────

def test_empty_place_list_returns_empty_result():
    result = _run([])
    assert result.days == []
    assert result.total_distance_km == 0.0
    assert result.warnings == []
    assert result.optimization_score == 100.0


# ─── Edge case: one place ───────────────────────────────────────────────────

def test_single_place_is_scheduled_at_day_start():
    result = _run([_place(1, "Ayasofya", 41.0086, 28.9802)])
    assert len(result.days) == 1
    day = result.days[0]
    assert len(day.stops) == 1
    stop = day.stops[0]
    assert stop.day_index == 0
    assert stop.order_index == 0
    assert stop.arrival_time == "09:00"
    assert stop.travel_time_to_next_minutes is None
    assert stop.travel_distance_to_next_km is None
    assert result.total_distance_km == 0.0


def test_single_place_without_hours_gets_unavailable_warning():
    result = _run([_place(1, "Ayasofya", 41.0086, 28.9802)])
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)
    # skor: 100 - 0 (seyahat) - 5 (1 uyarı) = 95
    assert result.optimization_score == 95.0


# ─── Category-based visit duration ──────────────────────────────────────────

def test_museum_category_gets_longer_visit_duration_than_default():
    result = _run([_place(1, "Müze", 41.0, 29.0, category="museum")])
    assert result.days[0].stops[0].visit_duration_minutes == 90


def test_unknown_category_falls_back_to_default_duration():
    result = _run([_place(1, "Bilinmeyen", 41.0, 29.0, category="not-a-real-category")])
    assert result.days[0].stops[0].visit_duration_minutes == 60


# ─── Duplicate handling is NOT the strategy's job ───────────────────────────

def test_strategy_does_not_dedupe_by_itself():
    """Dedup, OptimizationService'in sorumluluğu (bkz. test_trip_optimization.py)
    — strateji kendisine verilen listeyi olduğu gibi işler."""
    p = _place(1, "Aynı Mekan", 41.0, 29.0)
    result = _run([p, p])
    assert sum(len(d.stops) for d in result.days) == 2


# ─── Multiple cities → long travel segment warning ──────────────────────────

def test_multiple_cities_triggers_long_travel_segment_warning():
    istanbul = [
        _place(1, "Ayasofya", 41.0086, 28.9802),
        _place(2, "Topkapı Sarayı", 41.0115, 28.9833),
    ]
    cappadocia = [
        _place(3, "Göreme Açık Hava Müzesi", 38.6425, 34.8288),
        _place(4, "Uçhisar Kalesi", 38.6297, 34.8117),
    ]
    result = _run(istanbul + cappadocia)
    assert any("uzun bir seyahat segmenti" in w for w in result.warnings)
    # nearest-neighbor kümeyi bitirmeden sıçramamalı: rota bir şehri tam
    # gezmeden diğerine atlamaz.
    ordered_ids = [stop.place_id for day in result.days for stop in day.stops]
    first_two, last_two = set(ordered_ids[:2]), set(ordered_ids[2:])
    assert first_two in ({1, 2}, {3, 4})
    assert last_two in ({1, 2}, {3, 4})
    assert first_two != last_two


# ─── Opening hours: available and respected ─────────────────────────────────

def test_arrival_before_opening_is_clipped_silently():
    result = _run([_place(1, "Geç Açılan Mekan", 41.0, 29.0, opening_hours="10:00-18:00")])
    stop = result.days[0].stops[0]
    assert stop.arrival_time == "10:00"
    assert not any("çakışıyor" in w for w in result.warnings)


def test_arrival_after_closing_gets_conflict_warning():
    # preferred_start_time 09:00, mekan 07:00-08:00 arası açık — 09:00'da zaten kapalı.
    result = _run([_place(1, "Erken Kapanan Mekan", 41.0, 29.0, opening_hours="07:00-08:00")])
    assert any("çakışıyor" in w for w in result.warnings)


def test_missing_opening_hours_does_not_generate_conflict_warning():
    result = _run([_place(1, "Bilinmeyen Saat", 41.0, 29.0)])
    assert not any("çakışıyor" in w for w in result.warnings)
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)


# ─── Day splitting ───────────────────────────────────────────────────────────

def test_places_split_across_days_when_day_budget_exceeded():
    # 5 mekan x 90 dk (museum) = 450 dk/gün bütçesi (09:00-18:00 = 540 dk) içine
    # en fazla 6 sığar ama seyahat süresi de eklenince günün geri kalanı taşar.
    places = [_place(i, f"Müze {i}", 41.0 + i * 0.2, 29.0 + i * 0.2, category="museum") for i in range(8)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="12:00")
    assert len(result.days) > 1
    total_stops = sum(len(d.stops) for d in result.days)
    assert total_stops == 8  # hiçbir durak kaybolmamalı


def test_duration_days_not_provided_derives_day_count():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00", duration_days=None)
    assert len(result.days) >= 2


def test_duration_days_cap_forces_overflow_into_last_day_with_warning():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00", duration_days=1)
    assert len(result.days) == 1
    assert len(result.days[0].stops) == 6  # hiçbir durak düşürülmedi
    assert any("sığmayan duraklar" in w for w in result.warnings)


# ─── start_date → per-day calendar date ─────────────────────────────────────

def test_start_date_produces_calendar_dates_per_day():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(4)]
    result = _run(
        places, preferred_start_time="09:00", preferred_end_time="11:00",
        duration_days=None, start_date="2026-09-01",
    )
    assert result.days[0].date == "2026-09-01"
    if len(result.days) > 1:
        assert result.days[1].date == "2026-09-02"


def test_no_start_date_leaves_date_none():
    result = _run([_place(1, "Mekan", 41.0, 29.0)])
    assert result.days[0].date is None


# ─── Score bounds ────────────────────────────────────────────────────────────

def test_score_never_negative_even_with_many_warnings():
    # Şehirler-arası sıçramalarla dolu bir rota bolca uzun-segment uyarısı üretir.
    places = [
        _place(1, "A", 41.0, 29.0),
        _place(2, "B", 38.6, 34.8),   # ~700km
        _place(3, "C", 36.9, 30.7),   # Antalya
        _place(4, "D", 39.9, 32.8),   # Ankara
    ]
    result = _run(places)
    assert 0.0 <= result.optimization_score <= 100.0
