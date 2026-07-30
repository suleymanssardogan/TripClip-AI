"""
RouteOptimizer — haversine mesafe, mesafe matrisi, TSP (nearest-neighbor)
ve genel optimize_route akışı için testler. Kullanıcının analiz/paylaşım
sayfalarında gördüğü rota sırası ve toplam mesafe doğrudan bu koddan gelir.
"""
import math

import pytest

from app.ml.route_optimizer import RouteOptimizer


@pytest.fixture
def optimizer():
    return RouteOptimizer()


def _loc(name: str, lat: float, lng: float) -> dict:
    return {"original_name": name, "place_data": {"location": {"lat": lat, "lng": lng}}}


# ─── haversine_distance ─────────────────────────────────────────────────────

def test_haversine_distance_same_point_is_zero(optimizer):
    assert optimizer.haversine_distance(37.06, 37.38, 37.06, 37.38) == 0.0


def test_haversine_distance_known_city_pair(optimizer):
    # İstanbul (41.0082, 28.9784) → Ankara (39.9334, 32.8597), gerçek kuş
    # uçuşu mesafe ~350km. Formülün doğru çalıştığını makul bir toleransla
    # doğrular (haritadan ölçülen referans, tam ondalık hassasiyet gerekmez).
    dist = optimizer.haversine_distance(41.0082, 28.9784, 39.9334, 32.8597)
    assert 340 <= dist <= 360


def test_haversine_distance_is_symmetric(optimizer):
    a = optimizer.haversine_distance(37.06, 37.38, 36.88, 30.70)
    b = optimizer.haversine_distance(36.88, 30.70, 37.06, 37.38)
    assert a == b


# ─── build_distance_matrix ───────────────────────────────────────────────────

def test_build_distance_matrix_shape_and_diagonal(optimizer):
    locations = [_loc("A", 37.0, 37.0), _loc("B", 37.1, 37.1), _loc("C", 37.2, 37.2)]
    matrix = optimizer.build_distance_matrix(locations)

    assert len(matrix) == 3
    assert all(len(row) == 3 for row in matrix)
    assert all(matrix[i][i] == 0.0 for i in range(3))


def test_build_distance_matrix_is_symmetric(optimizer):
    locations = [_loc("A", 37.0, 37.0), _loc("B", 38.0, 38.0)]
    matrix = optimizer.build_distance_matrix(locations)
    assert matrix[0][1] == matrix[1][0]
    assert matrix[0][1] > 0


# ─── nearest_neighbor_tsp ────────────────────────────────────────────────────

def test_nearest_neighbor_tsp_single_location_returns_as_is(optimizer):
    locations = [_loc("Only", 37.0, 37.0)]
    matrix = optimizer.build_distance_matrix(locations)
    assert optimizer.nearest_neighbor_tsp(locations, matrix) == locations


def test_nearest_neighbor_tsp_visits_nearest_point_first():
    optimizer = RouteOptimizer()
    # A'dan başlar; B, C'den çok daha yakın olmalı → sıra A, B, C.
    locations = [_loc("A", 0.0, 0.0), _loc("C", 0.0, 10.0), _loc("B", 0.0, 1.0)]
    matrix = optimizer.build_distance_matrix(locations)

    route = optimizer.nearest_neighbor_tsp(locations, matrix)

    assert [loc["original_name"] for loc in route] == ["A", "B", "C"]


def test_nearest_neighbor_tsp_visits_every_location_exactly_once(optimizer):
    locations = [_loc(f"L{i}", i * 0.1, i * 0.1) for i in range(6)]
    matrix = optimizer.build_distance_matrix(locations)

    route = optimizer.nearest_neighbor_tsp(locations, matrix)

    assert sorted(loc["original_name"] for loc in route) == sorted(loc["original_name"] for loc in locations)
    assert len(route) == len(locations)


# ─── optimize_route ───────────────────────────────────────────────────────────

def test_optimize_route_empty_list(optimizer):
    result = optimizer.optimize_route([])
    assert result == {"route": [], "total_distance_km": 0, "stops": 0}


def test_optimize_route_single_location_has_zero_distance(optimizer):
    locations = [_loc("Only", 37.0, 37.0)]
    result = optimizer.optimize_route(locations)
    assert result["total_distance_km"] == 0
    assert result["stops"] == 1
    assert result["route"] == locations


def test_optimize_route_multiple_locations_reports_positive_total_distance(optimizer):
    locations = [_loc("A", 37.0, 37.0), _loc("B", 38.0, 38.0), _loc("C", 39.0, 39.0)]
    result = optimizer.optimize_route(locations)

    assert result["stops"] == 3
    assert result["total_distance_km"] > 0
    assert len(result["route"]) == 3


def test_optimize_route_matches_manual_distance_sum(optimizer):
    locations = [_loc("A", 0.0, 0.0), _loc("B", 0.0, 1.0), _loc("C", 0.0, 2.0)]
    result = optimizer.optimize_route(locations)

    route = result["route"]
    manual_total = sum(
        optimizer.haversine_distance(
            route[i]["place_data"]["location"]["lat"], route[i]["place_data"]["location"]["lng"],
            route[i + 1]["place_data"]["location"]["lat"], route[i + 1]["place_data"]["location"]["lng"],
        )
        for i in range(len(route) - 1)
    )
    assert result["total_distance_km"] == round(manual_total, 2)
