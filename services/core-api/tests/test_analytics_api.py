"""
POST /internal/analytics/events testleri: doğrulama, server-only event
reddi, BackgroundTasks üzerinden async kayıt.
"""
from unittest import mock


def test_track_event_accepts_client_fireable_event(client, bff_headers):
    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        resp = client.post(
            "/internal/analytics/events",
            json={
                "event": "shared_trip_link_copied",
                "trip_id": 42,
                "platform": "web",
                "source": "hero_button",
            },
            headers=bff_headers,
        )

    assert resp.status_code == 202
    assert resp.json() == {"success": True}
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["trip_id"] == 42
    assert kwargs["platform"] == "web"
    assert kwargs["source"] == "hero_button"


def test_track_event_forwards_user_id_from_header_not_body(client, bff_headers, registered_user):
    """user_id istemci gövdesinden değil, BFF'in ilettiği x-user-id header'ından
    gelmeli — aksi halde herhangi bir istemci başka bir kullanıcı adına sahte
    event üretebilirdi."""
    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        client.post(
            "/internal/analytics/events",
            json={"event": "shared_trip_opened", "trip_id": 1, "platform": "web"},
            headers=bff_headers,
        )

    _, kwargs = mock_track.call_args
    assert kwargs["user_id"] == registered_user["user_id"]


def test_track_event_allows_anonymous_viewer(client):
    """Herkese açık bir paylaşım sayfasını gezen, giriş yapmamış biri için
    x-user-id header'ı hiç gönderilmez — user_id None olarak kaydedilmeli,
    istek reddedilmemeli."""
    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        resp = client.post(
            "/internal/analytics/events",
            json={"event": "shared_trip_opened", "trip_id": 1, "platform": "web"},
        )

    assert resp.status_code == 202
    _, kwargs = mock_track.call_args
    assert kwargs["user_id"] is None


def test_track_event_rejects_unknown_event_name(client, bff_headers):
    resp = client.post(
        "/internal/analytics/events",
        json={"event": "totally_made_up_event", "trip_id": 1, "platform": "web"},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ANALYTICS_EVENT"


def test_track_event_rejects_server_only_event_from_client(client, bff_headers):
    """CREATED/DELETED sunucunun zaten kontrol ettiği durum değişikliklerinden
    türetiliyor — istemciden kabul edilirse var olmayan bir trip için sahte
    olay üretilebilirdi."""
    resp = client.post(
        "/internal/analytics/events",
        json={"event": "shared_trip_created", "trip_id": 1, "platform": "web"},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ANALYTICS_EVENT"


def test_track_event_rejects_not_yet_wired_event(client, bff_headers):
    """invite_sent/declined/expired taksonomide tanımlı ama hiçbir tetikleyicisi
    yok — beacon'dan da kabul edilmemeli, aksi halde ürünte olmayan bir eylem
    için veri üretilir."""
    resp = client.post(
        "/internal/analytics/events",
        json={"event": "shared_trip_declined", "trip_id": 1, "platform": "web"},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ANALYTICS_EVENT"
