"""
Web BFF — Trip sharing (davet) proxy testleri.
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


def test_preview_share_no_auth_required(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "trip_title": "Kapadokya Turu", "stops_count": 4, "role": "viewer",
    })
    resp = client.get("/api/web/shares/some-token/preview")
    assert resp.status_code == 200
    assert resp.json()["trip_title"] == "Kapadokya Turu"


def test_preview_share_invalid_token_propagates_404(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "SHARE_TOKEN_INVALID", "message": "invalid"}}
    )
    resp = client.get("/api/web/shares/bogus/preview")
    assert resp.status_code == 404
    assert resp.json()["code"] == "SHARE_TOKEN_INVALID"


def test_accept_share_requires_login(client):
    resp = client.post("/api/web/shares/accept", json={"token": "abc"})
    assert resp.status_code == 401


def test_accept_share_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"trip_id": 7})
    resp = client.post("/api/web/shares/accept", json={"token": "abc"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["trip_id"] == 7

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["headers"]["x-user-id"] == "1"


def test_accept_share_self_invite_rejected(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "CANNOT_JOIN_OWN_TRIP", "message": "own trip"}}
    )
    resp = client.post("/api/web/shares/accept", json={"token": "abc"}, headers=auth_headers)
    assert resp.status_code == 400


def test_decline_share_requires_login(client):
    resp = client.post("/api/web/shares/decline", json={"token": "abc"})
    assert resp.status_code == 401


def test_decline_share_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"success": True})
    resp = client.post("/api/web/shares/decline", json={"token": "abc"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
