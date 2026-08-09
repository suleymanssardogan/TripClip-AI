"""
ORToolsRouteOptimizationStrategy birim testleri — DB/HTTP yok, yalnızca
strateji. GreedyDistanceStrategy'nin kendi test dosyasıyla
(test_optimization_strategy.py) aynı fixture deseni ve — mümkün olduğunca —
aynı test senaryoları, böylece iki stratejinin aynı sözleşmeyi (hiçbir durak
kaybolmaz, aynı OptimizationResult şekli, aynı uyarı metinleri) sağladığı
doğrudan görülebilir. Ek olarak: determinism ve büyük durak kümeleri, bu
stratejiye özgü riskler (solver, greedy'nin aksine potansiyel olarak
zamanlama/rastgelelik taşıyabilir — bkz. ortools_strategy.py "Determinism").

Servis/repository katmanı test_trip_optimization.py'de (entegrasyon).
İki stratejinin şema uyumluluğu test_strategy_comparison.py'de.
"""
import time

from app.domain.optimization.models import PlaceInput, OptimizationConstraints
from app.infrastructure.optimization.ortools_strategy import ORToolsRouteOptimizationStrategy


def _place(place_id, name, lat, lng, category=None, opening_hours=None) -> PlaceInput:
    return PlaceInput(place_id=place_id, name=name, lat=lat, lng=lng, category=category, opening_hours=opening_hours)


def _run(places, **overrides):
    constraints = OptimizationConstraints(**overrides)
    return ORToolsRouteOptimizationStrategy().optimize(places, constraints)


def test_strategy_name_is_ortools():
    assert ORToolsRouteOptimizationStrategy().name == "ortools"


# ─── Edge case: 0 places ────────────────────────────────────────────────────

def test_empty_place_list_returns_empty_result():
    result = _run([])
    assert result.days == []
    assert result.total_distance_km == 0.0
    assert result.warnings == []
    assert result.optimization_score == 100.0


# ─── Edge case: 1 place ─────────────────────────────────────────────────────

def test_single_place_is_scheduled_at_day_start():
    result = _run([_place(1, "Ayasofya", 41.0086, 28.9802)])
    assert len(result.days) == 1
    stop = result.days[0].stops[0]
    assert stop.day_index == 0
    assert stop.order_index == 0
    assert stop.arrival_time == "09:00"
    assert stop.travel_time_to_next_minutes is None
    assert stop.travel_distance_to_next_km is None
    assert result.total_distance_km == 0.0


# ─── Edge case: 2 places ────────────────────────────────────────────────────

def test_two_places_both_scheduled():
    # n<=2 solver'ı hiç devreye sokmadan kısa devre yapar (bkz.
    # ortools_strategy._solve_visit_order) — yine de sözleşme aynı: her iki
    # durak da kaybolmadan planlanmalı.
    result = _run([
        _place(1, "A", 41.0, 29.0),
        _place(2, "B", 41.05, 29.05),
    ])
    ids = {stop.place_id for day in result.days for stop in day.stops}
    assert ids == {1, 2}
    assert sum(len(d.stops) for d in result.days) == 2


# ─── Duplicate handling is NOT the strategy's job ───────────────────────────

def test_strategy_does_not_dedupe_by_itself():
    """Dedup, OptimizationService'in sorumluluğu (bkz.
    test_optimization_strategy.py'deki aynı testin greedy karşılığı) —
    strateji kendisine verilen listeyi olduğu gibi işler."""
    p = _place(1, "Aynı Mekan", 41.0, 29.0)
    result = _run([p, p])
    assert sum(len(d.stops) for d in result.days) == 2


# ─── Multiple cities ─────────────────────────────────────────────────────────

def test_multiple_cities_all_places_represented_no_duplicates():
    istanbul = [
        _place(1, "Ayasofya", 41.0086, 28.9802),
        _place(2, "Topkapı Sarayı", 41.0115, 28.9833),
    ]
    cappadocia = [
        _place(3, "Göreme Açık Hava Müzesi", 38.6425, 34.8288),
        _place(4, "Uçhisar Kalesi", 38.6297, 34.8117),
    ]
    result = _run(istanbul + cappadocia)
    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == [1, 2, 3, 4]
    assert len(ids) == len(set(ids))


# ─── Impossible constraints ──────────────────────────────────────────────────

def test_impossible_day_budget_still_returns_all_stops_with_warning():
    """1 saatlik gün bütçesine 6 müze (90dk/tanesi) sığmaz — greedy'nin
    'forced last day overflow' davranışıyla aynı sözleşme: hiçbir durak
    düşürülmez, bunun yerine bir uyarı eklenir (fail gracefully)."""
    places = [_place(i, f"Müze {i}", 41.0 + i * 0.3, 29.0 + i * 0.3, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:00", duration_days=1)
    assert len(result.days) == 1
    assert len(result.days[0].stops) == 6
    assert any("sığmayan duraklar" in w for w in result.warnings)


def test_invalid_time_window_falls_back_to_default_window():
    """end_time <= start_time normalde OptimizationService'te reddedilir,
    ama strateji tek başına çağrılırsa çökmez, sessizce varsayılana düşer —
    greedy ile birebir aynı savunma."""
    result = _run([_place(1, "A", 41.0, 29.0)], preferred_start_time="18:00", preferred_end_time="09:00")
    assert result.days[0].stops[0].arrival_time == "09:00"


# ─── Unavailable / degenerate coordinates ───────────────────────────────────

def test_identical_coordinates_all_places_still_scheduled():
    """Aynı koordinata sahip birden çok mekan (ör. konum verisi eksik/varsayılan
    olduğunda) — mesafe her çift için 0, solver'ın çökmemesi/atlamaması gerekir."""
    places = [_place(i, f"Mekan {i}", 41.0, 29.0) for i in range(5)]
    result = _run(places)
    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == [0, 1, 2, 3, 4]
    assert result.total_distance_km == 0.0


# ─── Opening hours unavailable ───────────────────────────────────────────────

def test_missing_opening_hours_generates_unavailable_warning_not_conflict():
    result = _run([_place(1, "Bilinmeyen Saat", 41.0, 29.0)])
    assert not any("çakışıyor" in w for w in result.warnings)
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)


def test_arrival_before_opening_is_clipped_silently():
    result = _run([_place(1, "Geç Açılan Mekan", 41.0, 29.0, opening_hours="10:00-18:00")])
    stop = result.days[0].stops[0]
    assert stop.arrival_time == "10:00"
    assert not any("çakışıyor" in w for w in result.warnings)


def test_arrival_after_closing_gets_conflict_warning():
    result = _run([_place(1, "Erken Kapanan Mekan", 41.0, 29.0, opening_hours="07:00-08:00")])
    assert any("çakışıyor" in w for w in result.warnings)


# ─── Multiple days ────────────────────────────────────────────────────────────

def test_places_split_across_days_when_day_budget_exceeded():
    places = [_place(i, f"Müze {i}", 41.0 + i * 0.2, 29.0 + i * 0.2, category="museum") for i in range(8)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="12:00")
    assert len(result.days) > 1
    assert sum(len(d.stops) for d in result.days) == 8


def test_duration_days_not_provided_derives_day_count():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00", duration_days=None)
    assert len(result.days) >= 2


def test_start_date_produces_calendar_dates_per_day():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(4)]
    result = _run(
        places, preferred_start_time="09:00", preferred_end_time="11:00",
        duration_days=None, start_date="2026-09-01",
    )
    assert result.days[0].date == "2026-09-01"
    if len(result.days) > 1:
        assert result.days[1].date == "2026-09-02"


# ─── Large place sets ─────────────────────────────────────────────────────────

def test_large_place_set_completes_quickly_and_includes_every_place():
    places = [
        _place(i, f"Mekan {i}", 36.0 + (i % 17) * 0.3, 27.0 + ((i * 7) % 23) * 0.3)
        for i in range(60)
    ]
    start = time.monotonic()
    result = _run(places, duration_days=None)
    elapsed = time.monotonic() - start

    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == list(range(60))
    assert len(ids) == len(set(ids))
    # solution_limit-bound arama — gerçekçi gezi boyutlarında (onlarca durak)
    # saniyeler sürer, time_limit güvenlik ağına (5s) hiç yaklaşmaz.
    assert elapsed < 10.0


# ─── Score bounds ─────────────────────────────────────────────────────────────

def test_score_never_negative_even_with_many_warnings():
    places = [
        _place(1, "A", 41.0, 29.0),
        _place(2, "B", 38.6, 34.8),   # ~700km
        _place(3, "C", 36.9, 30.7),   # Antalya
        _place(4, "D", 39.9, 32.8),   # Ankara
    ]
    result = _run(places)
    assert 0.0 <= result.optimization_score <= 100.0


# ─── Determinism (bkz. ortools_strategy.py "Determinism") ───────────────────

def _stop_signature(result):
    return [
        (s.place_id, s.day_index, s.order_index, s.arrival_time, s.departure_time,
         s.travel_time_to_next_minutes, s.travel_distance_to_next_km)
        for day in result.days for s in day.stops
    ]


def test_same_input_produces_identical_result_across_repeated_runs():
    places = [
        _place(i, f"Mekan {i}", 41.0 + (i * 0.37) % 3, 29.0 + (i * 0.53) % 3,
               category=("museum" if i % 2 else None))
        for i in range(15)
    ]
    constraints = dict(
        preferred_start_time="09:00", preferred_end_time="18:00",
        duration_days=None, start_date="2026-09-01",
    )

    results = [_run(places, **constraints) for _ in range(5)]
    first_signature = _stop_signature(results[0])

    for other in results[1:]:
        assert _stop_signature(other) == first_signature
        assert other.total_distance_km == results[0].total_distance_km
        assert other.total_travel_time_minutes == results[0].total_travel_time_minutes
        assert other.optimization_score == results[0].optimization_score
        assert other.warnings == results[0].warnings


def test_determinism_holds_across_fresh_strategy_instances():
    """Strateji durumsuz (stateless) olmalı — yeni bir instance kullanmak
    sonucu değiştirmemeli. Registry'de tek bir paylaşılan instance var, ama
    bu varsayımı hiç kanıtlamadan bırakmayalım."""
    places = [_place(i, f"Mekan {i}", 40.0 + i * 0.4, 28.0 + i * 0.4) for i in range(10)]
    constraints = OptimizationConstraints()

    r1 = ORToolsRouteOptimizationStrategy().optimize(places, constraints)
    r2 = ORToolsRouteOptimizationStrategy().optimize(places, constraints)

    assert _stop_signature(r1) == _stop_signature(r2)
