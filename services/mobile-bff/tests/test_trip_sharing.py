"""
Mobile BFF — Trip sharing proxy testleri.
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


def test_create_share_requires_auth(client):
    resp = client.post("/api/mobile/trips/1/shares", json={"role": "viewer"})
    assert resp.status_code == 403


def test_create_share_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "share_id": 1, "trip_id": 1, "role": "viewer", "status": "pending",
        "created_at": None, "responded_at": None, "expires_at": None,
        "max_uses": None, "use_count": 0, "revoked": False,
        "token": "raw-token-abc", "share_url": "http://localhost:3000/invite/raw-token-abc",
    })

    resp = client.post(
        "/api/mobile/trips/1/shares", json={"role": "viewer"}, headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["token"] == "raw-token-abc"

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/trips/1/shares")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_create_share_propagates_core_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_SHARE_REQUEST", "message": "bad role"}}
    )
    resp = client.post("/api/mobile/trips/1/shares", json={"role": "admin"}, headers=auth_headers)
    assert resp.status_code == 400


def test_list_shares(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"shares": []})
    resp = client.get("/api/mobile/trips/1/shares", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"shares": []}


def test_revoke_share(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"success": True})
    resp = client.post("/api/mobile/trips/1/shares/5/revoke", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}


def test_preview_share_no_auth_required(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "trip_title": "Fethiye Turu", "stops_count": 3, "role": "editor",
    })
    resp = client.get("/api/mobile/shares/some-token/preview")
    assert resp.status_code == 200
    assert resp.json()["trip_title"] == "Fethiye Turu"


def test_preview_share_propagates_invalid_token_error(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(
        404, {"error": {"code": "SHARE_TOKEN_INVALID", "message": "invalid"}}
    )
    resp = client.get("/api/mobile/shares/bogus/preview")
    assert resp.status_code == 404


def test_accept_share_requires_auth(client):
    resp = client.post("/api/mobile/shares/accept", json={"token": "abc"})
    assert resp.status_code == 403


def test_accept_share_forwards_user_id(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"trip_id": 42})
    resp = client.post("/api/mobile/shares/accept", json={"token": "abc"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["trip_id"] == 42

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["headers"]["x-user-id"] == "1"
    assert kwargs["json"] == {"token": "abc"}


def test_decline_share(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"success": True})
    resp = client.post("/api/mobile/shares/decline", json={"token": "abc"}, headers=auth_headers)
    assert resp.status_code == 200


def test_list_collaborators(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"collaborators": []})
    resp = client.get("/api/mobile/trips/1/collaborators", headers=auth_headers)
    assert resp.status_code == 200


def test_remove_collaborator(client, auth_headers, mock_core_api, make_response):
    mock_core_api.delete.return_value = make_response(200, {"success": True})
    resp = client.delete("/api/mobile/trips/1/collaborators/7", headers=auth_headers)
    assert resp.status_code == 200
