"""
Mobile BFF — analytics event proxy testleri.
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


def test_track_event_requires_auth(client):
    resp = client.post(
        "/api/mobile/analytics/events",
        json={"event": "shared_trip_share_sheet_opened", "trip_id": 1},
    )
    assert resp.status_code == 403


def test_track_event_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(202, {"success": True})

    resp = client.post(
        "/api/mobile/analytics/events",
        json={"event": "shared_trip_share_sheet_opened", "trip_id": 42, "source": "results_menu"},
        headers=auth_headers,
    )

    assert resp.status_code == 202
    assert resp.json() == {"success": True}


def test_track_event_hardcodes_ios_platform(client, auth_headers, mock_core_api, make_response):
    """platform istemciden gelmez — mobile-bff olduğu için her zaman 'ios'."""
    mock_core_api.post.return_value = make_response(202, {"success": True})

    client.post(
        "/api/mobile/analytics/events",
        json={"event": "shared_trip_share_sheet_opened", "trip_id": 42},
        headers=auth_headers,
    )

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["json"]["platform"] == "ios"


def test_track_event_forwards_user_id_header(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(202, {"success": True})

    client.post(
        "/api/mobile/analytics/events",
        json={"event": "shared_trip_share_sheet_opened", "trip_id": 42},
        headers=auth_headers,
    )

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/analytics/events")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_track_event_propagates_core_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_ANALYTICS_EVENT", "message": "bilinmeyen event"}}
    )

    resp = client.post(
        "/api/mobile/analytics/events",
        json={"event": "not_a_real_event", "trip_id": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 400
