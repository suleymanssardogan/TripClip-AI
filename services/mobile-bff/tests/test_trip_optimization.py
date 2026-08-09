"""
Mobile BFF — AI Trip Optimizer proxy testleri.
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture) —
trip_sharing testleriyle aynı desen. Dört kategori: auth, unit (route/forwarding
davranışı), entegrasyon (DTO uyumluluğu), hata yayılımı (error propagation).
"""
import httpx


# ─── Authentication ───────────────────────────────────────────────────────────

def test_optimize_requires_auth(client):
    resp = client.post("/api/mobile/trips/1/optimize", json={"selected_place_ids": [1]})
    assert resp.status_code == 403  # HTTPBearer(auto_error=True) mobile-bff'de — bkz. app/core/auth.py


def test_list_itineraries_requires_auth(client):
    resp = client.get("/api/mobile/trips/1/itineraries")
    assert resp.status_code == 403


def test_get_itinerary_requires_auth(client):
    resp = client.get("/api/mobile/itineraries/1")
    assert resp.status_code == 403


# ─── Unit: route/forwarding davranışı ──────────────────────────────────────────

def test_optimize_trip_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "id": 4, "trip_id": 1, "strategy_name": "greedy_distance",
        "optimization_score": 87.5, "total_distance_km": 12.4,
        "total_travel_time_minutes": 29.8, "warnings": [], "created_at": None,
        "days": [],
    })

    resp = client.post(
        "/api/mobile/trips/1/optimize",
        json={"selected_place_ids": [12, 7, 19]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == 4

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/trips/1/optimize")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_list_itineraries_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"itineraries": []})

    resp = client.get("/api/mobile/trips/1/itineraries", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"itineraries": []}

    args, kwargs = mock_core_api.get.call_args
    assert args[0].endswith("/internal/trips/1/itineraries")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_get_itinerary_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"id": 4, "trip_id": 1, "days": []})

    resp = client.get("/api/mobile/itineraries/4", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == 4

    args, kwargs = mock_core_api.get.call_args
    assert args[0].endswith("/internal/itineraries/4")
    assert kwargs["headers"]["x-user-id"] == "1"


# ─── Entegrasyon: request/response DTO uyumluluğu ──────────────────────────────

def test_optimize_forwards_all_optional_fields(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "id": 1, "trip_id": 1, "strategy_name": "greedy_distance",
        "optimization_score": 90.0, "total_distance_km": 5.0,
        "total_travel_time_minutes": 12.0, "warnings": [], "created_at": None, "days": [],
    })

    body = {
        "selected_place_ids": [1, 2],
        "start_date": "2026-09-01",
        "duration_days": 2,
        "preferred_start_time": "10:00",
        "preferred_end_time": "20:00",
        "strategy": "greedy_distance",
    }
    resp = client.post("/api/mobile/trips/1/optimize", json=body, headers=auth_headers)
    assert resp.status_code == 200

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["json"] == body


def test_optimize_defaults_match_core_api_defaults(client, auth_headers, mock_core_api, make_response):
    """selected_place_ids dışında hiçbir alan verilmezse, core-api'nin
    OptimizeTripRequest'iyle birebir aynı varsayılanlar forward edilmeli
    (bkz. services/core-api/app/application/dto/optimization_dto.py)."""
    mock_core_api.post.return_value = make_response(200, {
        "id": 1, "trip_id": 1, "strategy_name": "greedy_distance",
        "optimization_score": 90.0, "total_distance_km": 0.0,
        "total_travel_time_minutes": 0.0, "warnings": [], "created_at": None, "days": [],
    })

    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": [1]}, headers=auth_headers,
    )
    assert resp.status_code == 200

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["json"] == {
        "selected_place_ids": [1],
        "start_date": None,
        "duration_days": None,
        "preferred_start_time": "09:00",
        "preferred_end_time": "18:00",
        "strategy": "greedy_distance",
    }


def test_optimize_response_body_passthrough_unchanged(client, auth_headers, mock_core_api, make_response):
    """BFF, core-api'nin döndürdüğü gövdeyi dönüştürmeden aynen iletir —
    optimizasyon mantığı yalnızca core-api'de yaşar."""
    upstream_body = {
        "id": 9, "trip_id": 1, "strategy_name": "greedy_distance",
        "optimization_score": 73.2, "total_distance_km": 44.1,
        "total_travel_time_minutes": 105.6,
        "warnings": ["Açılış saatleri bilinmiyor: 2 mekan için program bu kısıt dikkate alınmadan oluşturuldu."],
        "created_at": "2026-08-08T10:00:00",
        "days": [{"day_index": 0, "stops": [{
            "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
            "day_index": 0, "order_index": 0,
            "arrival_time": "09:00", "departure_time": "09:30",
            "visit_duration_minutes": 30,
            "travel_time_to_next_minutes": 4.2, "travel_distance_to_next_km": 1.75,
        }]}],
    }
    mock_core_api.post.return_value = make_response(200, upstream_body)

    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": [12]}, headers=auth_headers,
    )
    assert resp.json() == upstream_body


# ─── Hata yayılımı (error propagation) ─────────────────────────────────────────

def test_optimize_propagates_invalid_request_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_OPTIMIZATION_REQUEST", "message": "En az bir mekan seçmelisiniz."}}
    )
    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": []}, headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_optimize_propagates_trip_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "not found"}}
    )
    resp = client.post(
        "/api/mobile/trips/999/optimize", json={"selected_place_ids": [1]}, headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "TRIP_NOT_FOUND"


def test_optimize_propagates_permission_denied_as_403(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        403, {"error": {"code": "PERMISSION_DENIED", "message": "forbidden"}}
    )
    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": [1]}, headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "PERMISSION_DENIED"


def test_get_itinerary_propagates_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "ITINERARY_NOT_FOUND", "message": "not found"}}
    )
    resp = client.get("/api/mobile/itineraries/999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ITINERARY_NOT_FOUND"


def test_list_itineraries_propagates_trip_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "not found"}}
    )
    resp = client.get("/api/mobile/trips/999/itineraries", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "TRIP_NOT_FOUND"


def test_optimize_propagates_upstream_internal_error_as_500(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        500, {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "boom"}}
    )
    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": [1]}, headers=auth_headers,
    )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_SERVER_ERROR"


def test_optimize_core_api_unreachable_returns_503(client, auth_headers, mock_core_api):
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")

    resp = client.post(
        "/api/mobile/trips/1/optimize", json={"selected_place_ids": [1]}, headers=auth_headers,
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


# ─── apply_itinerary ────────────────────────────────────────────────────────

def test_apply_itinerary_requires_auth(client):
    resp = client.post("/api/mobile/itineraries/4/apply")
    assert resp.status_code == 403


def test_apply_itinerary_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "trip_id": 1, "itinerary_id": 4,
        "stops": [{"place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
                   "city": None, "category": None, "day_index": 0, "order_index": 0}],
        "stops_count": 1, "applied_at": "2026-08-09T10:00:00",
    })

    resp = client.post("/api/mobile/itineraries/4/apply", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trip_id"] == 1
    assert data["itinerary_id"] == 4
    assert data["stops_count"] == 1

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/itineraries/4/apply")
    assert kwargs["headers"]["x-user-id"] == "1"
    # Gövde göndermez — core-api'nin apply endpoint'i de almıyor.
    assert "json" not in kwargs or kwargs.get("json") is None


def test_apply_itinerary_propagates_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        404, {"error": {"code": "ITINERARY_NOT_FOUND", "message": "not found"}}
    )
    resp = client.post("/api/mobile/itineraries/999/apply", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ITINERARY_NOT_FOUND"


def test_apply_itinerary_propagates_permission_denied_as_403(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        403, {"error": {"code": "PERMISSION_DENIED", "message": "forbidden"}}
    )
    resp = client.post("/api/mobile/itineraries/4/apply", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "PERMISSION_DENIED"


def test_apply_itinerary_propagates_invalid_request_as_400(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_OPTIMIZATION_REQUEST", "message": "silinmiş mekanlar içeriyor"}}
    )
    resp = client.post("/api/mobile/itineraries/4/apply", headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_apply_itinerary_core_api_unreachable_returns_503(client, auth_headers, mock_core_api):
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")

    resp = client.post("/api/mobile/itineraries/4/apply", headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
