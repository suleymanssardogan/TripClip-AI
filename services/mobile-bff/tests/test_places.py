"""
Mobile BFF — Place (kütüphane) endpoint testleri.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


# ─── Auth guard ───────────────────────────────────────────────────────────

def test_get_library_missing_jwt(client):
    resp = client.get("/api/mobile/places")
    assert resp.status_code == 403


def test_get_library_invalid_jwt(client):
    resp = client.get("/api/mobile/places", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# ─── Happy path ─────────────────────────────────────────────────────────────

def test_get_library_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "places": [{
            "id": 1, "name": "Kaputaş Plajı", "lat": 36.15, "lng": 29.45,
            "city": "Antalya", "address": "Kaputaş Plajı, Antalya",
            "category": None, "save_count": 2, "saved_at": "2026-08-06T10:00:00",
        }],
        "total": 1,
    })

    resp = client.get("/api/mobile/places", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    place = data["places"][0]
    # camelCase alanlara dönüştürülmeli (Swift Codable)
    assert place["latitude"] == 36.15
    assert place["longitude"] == 29.45
    assert place["saveCount"] == 2
    assert place["savedAt"] == "2026-08-06T10:00:00"


def test_get_library_forwards_user_id(client, auth_headers, mock_core_api, make_response):
    """user_id JWT'den türetilip x-user-id header'ıyla core-api'ye iletilmeli — istemciden değil."""
    mock_core_api.get.return_value = make_response(200, {"places": [], "total": 0})

    client.get("/api/mobile/places", headers=auth_headers)

    args, kwargs = mock_core_api.get.call_args
    assert args[0].endswith("/internal/places")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_get_library_forwards_query_params(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"places": [], "total": 0})

    client.get("/api/mobile/places?city=Antalya&q=plaj&limit=10&offset=5", headers=auth_headers)

    _, kwargs = mock_core_api.get.call_args
    assert kwargs["params"] == {"limit": 10, "offset": 5, "city": "Antalya", "q": "plaj"}


def test_get_library_omits_absent_filters(client, auth_headers, mock_core_api, make_response):
    """city/q verilmediyse core-api'ye boş string değil, hiç gönderilmemeli."""
    mock_core_api.get.return_value = make_response(200, {"places": [], "total": 0})

    client.get("/api/mobile/places", headers=auth_headers)

    _, kwargs = mock_core_api.get.call_args
    assert "city" not in kwargs["params"]
    assert "q" not in kwargs["params"]


def test_get_library_invalid_limit_rejected(client, auth_headers, mock_core_api):
    """limit>50 → core-api'ye hiç gidilmeden 422."""
    resp = client.get("/api/mobile/places?limit=9999", headers=auth_headers)
    assert resp.status_code == 422
    mock_core_api.get.assert_not_awaited()


def test_get_library_propagates_core_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        500, {"error": {"code": "DATABASE_ERROR", "message": "db down"}}
    )
    resp = client.get("/api/mobile/places", headers=auth_headers)
    assert resp.status_code == 500


# ─── Transformer ─────────────────────────────────────────────────────────────

def test_transformer_shapes_place_fields():
    from app.transformers.place_transformer import to_mobile_library

    out = to_mobile_library({
        "places": [{
            "id": 3, "name": "Kız Kulesi", "lat": 41.02, "lng": 29.0,
            "city": None, "address": None, "category": None,
            "save_count": 1, "saved_at": None,
        }],
        "total": 1,
    })
    place = out["places"][0]
    assert place["id"] == 3
    assert place["latitude"] == 41.02
    assert place["longitude"] == 29.0
    assert place["saveCount"] == 1


def test_transformer_empty_library():
    from app.transformers.place_transformer import to_mobile_library

    out = to_mobile_library({"places": [], "total": 0})
    assert out == {"places": [], "total": 0}
