"""
GreedyDistanceStrategy ile ORToolsRouteOptimizationStrategy'yi aynı
fixture'lar üzerinde karşılaştıran testler — bu milestone'un kendi hedefi
olan "strateji soyutlaması gerçekten değiştirilebilir mi" sorusunu doğrudan
sınar.

Bilerek İKİ STRATEJİNİN AYNI ROTAYI ÜRETMESİNİ İSTEMİYORUZ (spesifikasyonun
kendi kısıtı) — yalnızca ikisinin de aynı SÖZLEŞMEYİ sağladığını
doğruluyoruz: geçerli mekanlar, tekrarsız, mümkün olduğunda hiçbir durak
kaybolmaz, geçerli gün atamaları, aynı OptimizationResult şeması.
"""
import pytest

from app.domain.optimization.models import PlaceInput, OptimizationConstraints
from app.infrastructure.optimization.greedy_distance_strategy import GreedyDistanceStrategy
from app.infrastructure.optimization.ortools_strategy import ORToolsRouteOptimizationStrategy
from app.infrastructure.optimization.strategy_registry import (
    available_strategies, get_strategy, DEFAULT_STRATEGY_NAME,
)


def _place(place_id, name, lat, lng, category=None, opening_hours=None) -> PlaceInput:
    return PlaceInput(place_id=place_id, name=name, lat=lat, lng=lng, category=category, opening_hours=opening_hours)


def _strategies():
    """Her testte taze instance — determinism testlerindeki 'stateless
    olmalı' varsayımıyla tutarlı, iki test arasında sızıntı riski sıfır."""
    return [GreedyDistanceStrategy(), ORToolsRouteOptimizationStrategy()]


FIXTURES = {
    "single_place": [_place(1, "Ayasofya", 41.0086, 28.9802)],
    "small_set": [
        _place(1, "Ayasofya", 41.0086, 28.9802, category="landmark"),
        _place(2, "Topkapı Sarayı", 41.0115, 28.9833, category="museum"),
        _place(3, "Kapalıçarşı", 41.0106, 28.9681, category="shopping"),
    ],
    "multi_city": [
        _place(1, "Ayasofya", 41.0086, 28.9802),
        _place(2, "Topkapı Sarayı", 41.0115, 28.9833),
        _place(3, "Göreme Açık Hava Müzesi", 38.6425, 34.8288),
        _place(4, "Uçhisar Kalesi", 38.6297, 34.8117),
    ],
    "with_opening_hours": [
        _place(1, "A", 41.0, 29.0, opening_hours="09:00-18:00"),
        _place(2, "B", 41.02, 29.02, opening_hours="07:00-08:00"),  # çakışacak
        _place(3, "C", 41.04, 29.04),  # bilinmiyor
    ],
    "day_split_needed": [
        _place(i, f"Müze {i}", 41.0 + i * 0.2, 29.0 + i * 0.2, category="museum")
        for i in range(8)
    ],
    "duplicate_coordinates": [_place(i, f"Mekan {i}", 41.0, 29.0) for i in range(4)],
}


# ─── Registry sanity: ikisi de kayıtlı, greedy varsayılan olarak kalıyor ────

def test_both_strategies_registered():
    assert "greedy_distance" in available_strategies()
    assert "ortools" in available_strategies()


def test_greedy_distance_remains_the_default():
    assert DEFAULT_STRATEGY_NAME == "greedy_distance"
    assert isinstance(get_strategy(DEFAULT_STRATEGY_NAME), GreedyDistanceStrategy)


def test_ortools_resolvable_by_name_through_registry():
    assert isinstance(get_strategy("ortools"), ORToolsRouteOptimizationStrategy)


# ─── Schema parity — OptimizationResult şekli birebir aynı ──────────────────

@pytest.mark.parametrize("strategy", _strategies(), ids=lambda s: s.name)
@pytest.mark.parametrize("fixture_name", FIXTURES.keys())
def test_result_schema_matches_across_strategies(strategy, fixture_name):
    places = FIXTURES[fixture_name]
    result = strategy.optimize(places, OptimizationConstraints())

    assert isinstance(result.days, list)
    assert isinstance(result.total_distance_km, float)
    assert isinstance(result.total_travel_time_minutes, float)
    assert isinstance(result.optimization_score, float)
    assert isinstance(result.warnings, list)
    for day in result.days:
        assert isinstance(day.day_index, int)
        assert isinstance(day.stops, list)
        for stop in day.stops:
            assert isinstance(stop.place_id, int)
            assert isinstance(stop.name, str)
            assert isinstance(stop.lat, float)
            assert isinstance(stop.lng, float)
            assert isinstance(stop.day_index, int)
            assert isinstance(stop.order_index, int)
            assert isinstance(stop.visit_duration_minutes, int)
            assert stop.arrival_time is None or isinstance(stop.arrival_time, str)
            assert stop.departure_time is None or isinstance(stop.departure_time, str)


# ─── Behavioral invariants both strategies must satisfy ──────────────────────

@pytest.mark.parametrize("fixture_name", FIXTURES.keys())
def test_all_places_represented_no_duplicates(fixture_name):
    places = FIXTURES[fixture_name]
    expected_ids = sorted(p.place_id for p in places)

    for strategy in _strategies():
        result = strategy.optimize(places, OptimizationConstraints())
        got_ids = [stop.place_id for day in result.days for stop in day.stops]
        assert sorted(got_ids) == expected_ids, f"{strategy.name} durak kaybetti/kopyaladı: {fixture_name}"
        assert len(got_ids) == len(set(got_ids)), f"{strategy.name} tekrar üretti: {fixture_name}"


@pytest.mark.parametrize("fixture_name", FIXTURES.keys())
def test_day_assignments_are_valid(fixture_name):
    places = FIXTURES[fixture_name]
    for strategy in _strategies():
        result = strategy.optimize(places, OptimizationConstraints())
        day_indices = [d.day_index for d in result.days]
        assert day_indices == list(range(len(result.days))), strategy.name
        for day in result.days:
            order_indices = [s.order_index for s in day.stops]
            assert order_indices == list(range(len(day.stops))), strategy.name
            for s in day.stops:
                assert s.day_index == day.day_index


@pytest.mark.parametrize("fixture_name", FIXTURES.keys())
def test_score_within_bounds(fixture_name):
    places = FIXTURES[fixture_name]
    for strategy in _strategies():
        result = strategy.optimize(places, OptimizationConstraints())
        assert 0.0 <= result.optimization_score <= 100.0


def test_day_split_needed_fixture_both_strategies_split_across_multiple_days():
    """Aynı sıkı gün bütçesi altında ikisi de birden fazla güne bölmeli —
    farklı bir rota üretebilirler ama hiçbir durak kaybolamaz, gün sayısı
    sıfır/eksik olamaz."""
    places = FIXTURES["day_split_needed"]
    constraints = OptimizationConstraints(preferred_start_time="09:00", preferred_end_time="12:00")
    for strategy in _strategies():
        result = strategy.optimize(places, constraints)
        assert len(result.days) > 1, strategy.name
        assert sum(len(d.stops) for d in result.days) == len(places)


def test_unknown_place_category_both_strategies_fall_back_to_default_duration():
    places = [_place(1, "Bilinmeyen Tür", 41.0, 29.0, category="not-a-real-category")]
    for strategy in _strategies():
        result = strategy.optimize(places, OptimizationConstraints())
        assert result.days[0].stops[0].visit_duration_minutes == 60, strategy.name
