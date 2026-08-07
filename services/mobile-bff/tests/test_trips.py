"""
Mobile BFF — Trip endpoint testleri.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


# ─── Auth guard ───────────────────────────────────────────────────────────

def test_create_trip_missing_jwt(client):
    resp = client.post("/api/mobile/trips", json={"title": "X", "place_ids": [1]})
    assert resp.status_code == 403


def test_list_trips_missing_jwt(client):
    resp = client.get("/api/mobile/trips")
    assert resp.status_code == 403


# ─── Create ─────────────────────────────────────────────────────────────────

def test_create_trip_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "id": 5, "title": "Fethiye Turu", "total_distance_km": 12.3,
        "created_at": "2026-08-07T10:00:00", "stops_count": 2,
        "days": [[
            {"place_id": 1, "name": "Kaputaş Plajı", "lat": 36.15, "lng": 29.45,
             "city": "Antalya", "category": None, "day_index": 0, "order_index": 0},
            {"place_id": 2, "name": "Saklıkent Kanyonu", "lat": 36.52, "lng": 29.62,
             "city": "Antalya", "category": None, "day_index": 0, "order_index": 1},
        ]],
    })

    resp = client.post(
        "/api/mobile/trips",
        json={"title": "Fethiye Turu", "place_ids": [1, 2]},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fethiye Turu"
    assert data["totalDistanceKm"] == 12.3
    assert data["stopsCount"] == 2
    stop = data["days"][0][0]
    assert stop["placeId"] == 1
    assert stop["latitude"] == 36.15
    assert stop["longitude"] == 29.45
    assert stop["dayIndex"] == 0


def test_create_trip_forwards_user_id(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "id": 1, "title": "X", "total_distance_km": 0, "created_at": None,
        "stops_count": 1, "days": [[]],
    })

    client.post("/api/mobile/trips", json={"title": "X", "place_ids": [1]}, headers=auth_headers)

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/trips")
    assert kwargs["headers"]["x-user-id"] == "1"
    assert kwargs["json"] == {"title": "X", "place_ids": [1]}


def test_create_trip_propagates_core_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_TRIP_PLACES", "message": "boş"}}
    )
    resp = client.post("/api/mobile/trips", json={"title": "X", "place_ids": []}, headers=auth_headers)
    assert resp.status_code == 400


# ─── List / Detail ────────────────────────────────────────────────────────────

def test_list_trips_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "trips": [{"id": 1, "title": "Gezi", "total_distance_km": 5.0,
                   "created_at": "2026-08-07T10:00:00", "stops_count": 3}],
    })

    resp = client.get("/api/mobile/trips", headers=auth_headers)
    assert resp.status_code == 200
    trip = resp.json()["trips"][0]
    assert trip["totalDistanceKm"] == 5.0
    assert trip["stopsCount"] == 3


def test_get_trip_detail_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "id": 1, "title": "Gezi", "total_distance_km": 5.0,
        "created_at": None, "stops_count": 0, "days": [],
    })

    resp = client.get("/api/mobile/trips/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_get_trip_not_found_propagates(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "yok"}}
    )
    resp = client.get("/api/mobile/trips/999", headers=auth_headers)
    assert resp.status_code == 404


# ─── Reorder / Delete ─────────────────────────────────────────────────────────

def test_update_stop_order_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.patch.return_value = make_response(200, {"success": True})

    resp = client.patch(
        "/api/mobile/trips/1/order",
        json={"order": [[2, 1]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}

    _, kwargs = mock_core_api.patch.call_args
    assert kwargs["json"] == {"order": [[2, 1]]}


def test_delete_trip_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.delete.return_value = make_response(200, {"success": True})

    resp = client.delete("/api/mobile/trips/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}


# ─── Transformer ─────────────────────────────────────────────────────────────

def test_transformer_shapes_trip_detail():
    from app.transformers.trip_transformer import to_mobile_trip_detail

    out = to_mobile_trip_detail({
        "id": 1, "title": "Gezi", "total_distance_km": 3.2, "created_at": None,
        "stops_count": 1,
        "days": [[{"place_id": 9, "name": "X", "lat": 1.0, "lng": 2.0,
                    "city": None, "category": None, "day_index": 0, "order_index": 0}]],
    })
    stop = out["days"][0][0]
    assert stop["placeId"] == 9
    assert stop["latitude"] == 1.0
    assert stop["longitude"] == 2.0


def test_transformer_empty_trip_list():
    from app.transformers.trip_transformer import to_mobile_trip_list

    assert to_mobile_trip_list({"trips": []}) == {"trips": []}
