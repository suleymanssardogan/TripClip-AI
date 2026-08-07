"""
Web BFF — analytics event proxy testleri.
Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


def test_track_event_allows_anonymous_viewer(client, mock_core_api, make_response):
    """Herkese açık paylaşım sayfasını gezen, giriş yapmamış bir ziyaretçi
    de event gönderebilmeli — JWT zorunlu değil."""
    mock_core_api.post.return_value = make_response(202, {"success": True})

    resp = client.post(
        "/api/web/analytics/events",
        json={"event": "shared_trip_opened", "trip_id": 42},
    )

    assert resp.status_code == 202
    _, kwargs = mock_core_api.post.call_args
    assert "x-user-id" not in kwargs["headers"]


def test_track_event_forwards_user_id_when_authenticated(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(202, {"success": True})

    client.post(
        "/api/web/analytics/events",
        json={"event": "shared_trip_link_copied", "trip_id": 42, "source": "hero_button"},
        headers=auth_headers,
    )

    _, kwargs = mock_core_api.post.call_args
    assert kwargs["headers"]["x-user-id"] == "1"


def test_track_event_hardcodes_web_platform(client, mock_core_api, make_response):
    """platform istemciden gelmez — web-bff olduğu için her zaman 'web'."""
    mock_core_api.post.return_value = make_response(202, {"success": True})

    client.post(
        "/api/web/analytics/events",
        json={"event": "shared_trip_opened", "trip_id": 42},
    )

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/analytics/events")
    assert kwargs["json"]["platform"] == "web"


def test_track_event_propagates_core_error(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_ANALYTICS_EVENT", "message": "bilinmeyen event"}}
    )

    resp = client.post(
        "/api/web/analytics/events",
        json={"event": "not_a_real_event", "trip_id": 1},
    )
    assert resp.status_code == 400
