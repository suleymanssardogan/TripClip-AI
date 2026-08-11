"""
Web BFF — Trip proxy testleri (Milestone 21 — Web AI Trip Optimizer).
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api
fixture) — test_trip_optimization.py ile AYNI desen.
"""
import httpx


# ─── Authentication ───────────────────────────────────────────────────────────

def test_list_trips_requires_auth(client):
    resp = client.get("/api/web/trips")
    assert resp.status_code == 401


def test_get_trip_requires_auth(client):
    resp = client.get("/api/web/trips/1")
    assert resp.status_code == 401


# ─── Unit: route/forwarding davranışı ──────────────────────────────────────────

def test_list_trips_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"trips": [
        {"id": 1, "title": "İstanbul Gezisi", "total_distance_km": 12.4,
         "created_at": "2026-08-01T10:00:00", "stops_count": 3, "role": "owner"},
    ]})

    resp = client.get("/api/web/trips", headers=auth_headers)
    assert resp.status_code == 200
    trips = resp.json()["trips"]
    assert len(trips) == 1
    assert trips[0]["id"] == 1

    args, kwargs = mock_core_api.get.call_args
    assert args[0].endswith("/internal/trips")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_get_trip_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "id": 1, "title": "İstanbul Gezisi", "total_distance_km": 12.4,
        "created_at": "2026-08-01T10:00:00", "stops_count": 2, "owner_id": 1,
        "your_role": "owner", "applied_itinerary_id": None, "itinerary_applied_at": None,
        "days": [[
            {"place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
             "city": "İstanbul", "category": "tarihi", "day_index": 0, "order_index": 0},
        ]],
    })

    resp = client.get("/api/web/trips/1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["your_role"] == "owner"
    assert len(data["days"][0]) == 1

    args, kwargs = mock_core_api.get.call_args
    assert args[0].endswith("/internal/trips/1")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_get_trip_response_body_passthrough_unchanged(client, auth_headers, mock_core_api, make_response):
    """BFF, core-api'nin döndürdüğü gövdeyi dönüştürmeden aynen iletir —
    mobile-bff'in kendi camelCase trip_transformer'ı BURADA kullanılmıyor."""
    upstream_body = {
        "id": 4, "title": "Kapadokya Turu", "total_distance_km": 88.1,
        "created_at": "2026-08-05T09:00:00", "stops_count": 5, "owner_id": 2,
        "your_role": "editor", "applied_itinerary_id": 9, "itinerary_applied_at": "2026-08-06T10:00:00",
        "days": [[]],
    }
    mock_core_api.get.return_value = make_response(200, upstream_body)

    resp = client.get("/api/web/trips/4", headers=auth_headers)
    assert resp.json() == upstream_body


# ─── Hata yayılımı (error propagation) ─────────────────────────────────────────

def test_get_trip_propagates_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "not found"}}
    )
    resp = client.get("/api/web/trips/999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "TRIP_NOT_FOUND"


def test_list_trips_propagates_upstream_error_as_503(client, auth_headers, mock_core_api, make_response):
    """Web BFF INTERNAL_SERVER_ERROR'ı 503'e eşler (bkz. Milestone 19'un
    aynı bulgusu, `_parse_core_error`)."""
    mock_core_api.get.return_value = make_response(
        500, {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "boom"}}
    )
    resp = client.get("/api/web/trips", headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["code"] == "INTERNAL_SERVER_ERROR"


def test_get_trip_core_api_unreachable_returns_503(client, auth_headers, mock_core_api):
    mock_core_api.get.side_effect = httpx.ConnectError("connection refused")

    resp = client.get("/api/web/trips/1", headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
