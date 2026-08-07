"""
Trip sharing testleri: davet oluşturma/iptal, önizleme, kabul/reddet,
collaborator yönetimi, ve yetkilendirme (authorization) senaryoları.
"""
from datetime import datetime, timedelta
from unittest import mock

from conftest import TestingSessionLocal


def _make_video(user_id: int, filename: str = "clip.mp4") -> int:
    from app.models.video import Video, VideoStatus

    db = TestingSessionLocal()
    try:
        video = Video(
            filename=filename,
            file_path=f"/tmp/does-not-exist-{filename}",
            status=VideoStatus.UPLOADED,
            user_id=user_id,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id
    finally:
        db.close()


def _loc(name: str, lat: float, lng: float, city: str = "Antalya") -> dict:
    return {
        "original_name": name,
        "place_data": {
            "name": name,
            "location": {"lat": lat, "lng": lng},
            "address_details": {"city": city},
        },
    }


def _save_places(user_id: int, locations: list) -> None:
    from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository

    db = TestingSessionLocal()
    try:
        vid = _make_video(user_id)
        repo = SqlVideoRepository(db)
        repo.save_results(vid, {"deduplicated_locations": locations})
    finally:
        db.close()


def _library_place_ids(client, headers) -> list[int]:
    data = client.get("/internal/places", headers=headers).json()
    return [p["id"] for p in data["places"]]


def _make_trip(client, headers, title: str = "Test Gezisi") -> int:
    place_ids = _library_place_ids(client, headers)
    resp = client.post("/internal/trips", json={"title": title, "place_ids": place_ids}, headers=headers)
    return resp.json()["id"]


def _second_user(client) -> tuple[int, dict]:
    import uuid
    email = f"u2_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post("/internal/auth/register", json={"email": email, "password": "P2_test!"})
    uid = resp.json()["user_id"]
    return uid, {"x-user-id": str(uid)}


def _setup_trip_with_places(client, headers) -> int:
    uid = int(headers["x-user-id"])
    _save_places(uid, [_loc("Mekan A", 36.0, 29.0), _loc("Mekan B", 36.1, 29.1)])
    return _make_trip(client, headers)


# ─── create_share ─────────────────────────────────────────────────────────────

def test_create_share_returns_token_once(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)

    resp = client.post(
        f"/internal/trips/{trip_id}/shares",
        json={"role": "viewer"},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["role"] == "viewer"
    assert len(data["token"]) > 20
    assert data["token"] in data["share_url"]
    assert data["use_count"] == 0
    assert data["revoked"] is False


def test_create_share_only_owner(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    _, other_headers = _second_user(client)

    resp = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=other_headers,
    )
    assert resp.status_code == 404  # sızıntı önleme — 403 değil


def test_create_share_rejects_invalid_role(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    resp = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "admin"}, headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SHARE_REQUEST"


def test_create_share_rejects_past_expiry(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    resp = client.post(
        f"/internal/trips/{trip_id}/shares",
        json={"role": "viewer", "expires_at": past},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_create_share_rejects_zero_max_uses(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    resp = client.post(
        f"/internal/trips/{trip_id}/shares",
        json={"role": "viewer", "max_uses": 0},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_create_share_trip_not_found(client, bff_headers):
    resp = client.post("/internal/trips/999999/shares", json={"role": "viewer"}, headers=bff_headers)
    assert resp.status_code == 404


def test_create_share_fires_invite_sent_analytics(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        client.post(f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers)

    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["event"].value == "shared_trip_invite_sent"
    assert kwargs["trip_id"] == trip_id
    assert kwargs["kind"] == "trip"


# ─── list_shares / revoke_share ───────────────────────────────────────────────

def test_list_shares_owner_only(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    client.post(f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers)

    resp = client.get(f"/internal/trips/{trip_id}/shares", headers=bff_headers)
    assert resp.status_code == 200
    assert len(resp.json()["shares"]) == 1

    _, other_headers = _second_user(client)
    resp2 = client.get(f"/internal/trips/{trip_id}/shares", headers=other_headers)
    assert resp2.status_code == 404


def test_revoke_share_by_owner(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()

    resp = client.post(
        f"/internal/trips/{trip_id}/shares/{share['share_id']}/revoke", headers=bff_headers,
    )
    assert resp.status_code == 200

    shares = client.get(f"/internal/trips/{trip_id}/shares", headers=bff_headers).json()["shares"]
    assert shares[0]["status"] == "revoked"
    assert shares[0]["revoked"] is True


def test_revoke_share_rejects_non_owner(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    _, other_headers = _second_user(client)

    resp = client.post(
        f"/internal/trips/{trip_id}/shares/{share['share_id']}/revoke", headers=other_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_revoked_link_stops_working_immediately(client, bff_headers, registered_user):
    """Spesifikasyonun katı gereksinimi: revoke sonrası token'ın önizleme/kabul
    tarafında ANINDA işe yaramaz olması gerekir."""
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    token = share["token"]

    client.post(f"/internal/trips/{trip_id}/shares/{share['share_id']}/revoke", headers=bff_headers)

    resp = client.get(f"/internal/shares/{token}/preview")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SHARE_TOKEN_INVALID"


def test_revoke_share_not_found(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    resp = client.post(f"/internal/trips/{trip_id}/shares/999999/revoke", headers=bff_headers)
    assert resp.status_code == 404


# ─── preview_share ────────────────────────────────────────────────────────────

def test_preview_share_requires_no_auth(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers
    ).json()

    resp = client.get(f"/internal/shares/{share['token']}/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stops_count"] == 2
    assert data["role"] == "editor"


def test_preview_share_invalid_token(client):
    resp = client.get("/internal/shares/not-a-real-token/preview")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SHARE_TOKEN_INVALID"


def test_preview_share_does_not_leak_which_part_of_token_is_wrong(client, bff_headers, registered_user):
    """Geçersiz nedeni (yok/süresi dolmuş/iptal) HER ZAMAN aynı mesajla dönmeli
    — token tahmin etmeye çalışan biri hangi kısmın doğru olduğuna dair
    hiçbir sinyal almamalı."""
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    client.post(f"/internal/trips/{trip_id}/shares/{share['share_id']}/revoke", headers=bff_headers)

    revoked_resp = client.get(f"/internal/shares/{share['token']}/preview")
    garbage_resp = client.get("/internal/shares/totally-made-up/preview")

    assert revoked_resp.status_code == garbage_resp.status_code == 404
    assert revoked_resp.json()["error"]["message"] == garbage_resp.json()["error"]["message"]


def test_preview_respects_max_uses(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares",
        json={"role": "viewer", "max_uses": 2},
        headers=bff_headers,
    ).json()
    token = share["token"]

    assert client.get(f"/internal/shares/{token}/preview").status_code == 200
    assert client.get(f"/internal/shares/{token}/preview").status_code == 200
    # 3. deneme sınırı aşıyor.
    resp3 = client.get(f"/internal/shares/{token}/preview")
    assert resp3.status_code == 404


def test_expired_share_stops_working_and_fires_analytics(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)

    # Doğrudan DB'de geçmiş bir expires_at ile bir davet oluştur — API
    # gelecekteki bir tarih ister, bu yüzden testte geçmişe alıyoruz.
    from app.models.trip_share import TripShare
    from app.models.share_token import ShareToken
    from app.models.trip_share_enums import CollaboratorRole
    from app.core.auth import generate_secure_token, hash_token

    raw_token = generate_secure_token()
    db = TestingSessionLocal()
    try:
        share = TripShare(trip_id=trip_id, created_by=registered_user["user_id"], role=CollaboratorRole.VIEWER)
        db.add(share)
        db.flush()
        db.add(ShareToken(
            share_id=share.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        ))
        db.commit()
    finally:
        db.close()

    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        resp = client.get(f"/internal/shares/{raw_token}/preview")

    assert resp.status_code == 404
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["event"].value == "shared_trip_expired"
    assert kwargs["kind"] == "trip"


# ─── accept_share ─────────────────────────────────────────────────────────────

def test_accept_share_creates_collaborator_and_grants_access(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers
    ).json()
    invitee_id, invitee_headers = _second_user(client)

    resp = client.post(
        "/internal/shares/accept", json={"token": share["token"]}, headers=invitee_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["trip_id"] == trip_id

    detail = client.get(f"/internal/trips/{trip_id}", headers=invitee_headers).json()
    assert detail["your_role"] == "editor"

    shares = client.get(f"/internal/trips/{trip_id}/shares", headers=bff_headers).json()["shares"]
    assert shares[0]["status"] == "accepted"


def test_accept_share_requires_auth(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()

    resp = client.post("/internal/shares/accept", json={"token": share["token"]})
    assert resp.status_code == 401


def test_accept_share_twice_fails_second_time(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    _, invitee_headers = _second_user(client)

    first = client.post("/internal/shares/accept", json={"token": share["token"]}, headers=invitee_headers)
    assert first.status_code == 200

    second = client.post("/internal/shares/accept", json={"token": share["token"]}, headers=invitee_headers)
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "SHARE_TOKEN_INVALID"


def test_preview_then_accept_both_work_with_max_uses_one(client, bff_headers, registered_user):
    """Bir önceki tasarım hatasının regresyon testi: max_uses=1 iken önce
    önizleyip sonra kabul etmek çalışmalı — ikisi ayrı sayaçlar tüketmemeli."""
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares",
        json={"role": "viewer", "max_uses": 1},
        headers=bff_headers,
    ).json()
    _, invitee_headers = _second_user(client)

    preview = client.get(f"/internal/shares/{share['token']}/preview")
    assert preview.status_code == 200

    accept = client.post("/internal/shares/accept", json={"token": share["token"]}, headers=invitee_headers)
    assert accept.status_code == 200


def test_owner_cannot_accept_own_invite(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()

    resp = client.post("/internal/shares/accept", json={"token": share["token"]}, headers=bff_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_JOIN_OWN_TRIP"


def test_accept_invalid_token(client, bff_headers, registered_user):
    resp = client.post("/internal/shares/accept", json={"token": "bogus"}, headers=bff_headers)
    assert resp.status_code == 404


# ─── decline_share ────────────────────────────────────────────────────────────

def test_decline_share_marks_declined_and_fires_analytics(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    invitee_id, invitee_headers = _second_user(client)

    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        resp = client.post(
            "/internal/shares/decline", json={"token": share["token"]}, headers=invitee_headers,
        )
    assert resp.status_code == 200

    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["event"].value == "shared_trip_declined"
    assert kwargs["user_id"] == invitee_id
    assert kwargs["kind"] == "trip"

    # Reddeden kişi collaborator OLMAMALI.
    detail_resp = client.get(f"/internal/trips/{trip_id}", headers=invitee_headers)
    assert detail_resp.status_code == 404


def test_declined_token_cannot_be_accepted_afterward(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    _, invitee_headers = _second_user(client)

    client.post("/internal/shares/decline", json={"token": share["token"]}, headers=invitee_headers)
    resp = client.post("/internal/shares/accept", json={"token": share["token"]}, headers=invitee_headers)
    assert resp.status_code == 404


# ─── collaborators ────────────────────────────────────────────────────────────

def test_list_collaborators_visible_to_owner_and_members(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers
    ).json()
    collaborator_id, collaborator_headers = _second_user(client)
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=collaborator_headers)

    owner_view = client.get(f"/internal/trips/{trip_id}/collaborators", headers=bff_headers)
    assert owner_view.status_code == 200
    assert len(owner_view.json()["collaborators"]) == 1
    assert owner_view.json()["collaborators"][0]["user_id"] == collaborator_id
    assert owner_view.json()["collaborators"][0]["role"] == "editor"

    member_view = client.get(f"/internal/trips/{trip_id}/collaborators", headers=collaborator_headers)
    assert member_view.status_code == 200


def test_list_collaborators_hidden_from_strangers(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    _, stranger_headers = _second_user(client)

    resp = client.get(f"/internal/trips/{trip_id}/collaborators", headers=stranger_headers)
    assert resp.status_code == 404


def test_remove_collaborator_by_owner(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    collaborator_id, collaborator_headers = _second_user(client)
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=collaborator_headers)

    resp = client.delete(
        f"/internal/trips/{trip_id}/collaborators/{collaborator_id}", headers=bff_headers,
    )
    assert resp.status_code == 200

    # Erişim gerçekten kaldırılmış olmalı.
    assert client.get(f"/internal/trips/{trip_id}", headers=collaborator_headers).status_code == 404
    assert client.get(f"/internal/trips/{trip_id}/collaborators", headers=bff_headers).json()["collaborators"] == []


def test_remove_collaborator_rejects_non_owner(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    collaborator_id, collaborator_headers = _second_user(client)
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=collaborator_headers)

    _, stranger_headers = _second_user(client)
    resp = client.delete(
        f"/internal/trips/{trip_id}/collaborators/{collaborator_id}", headers=stranger_headers,
    )
    assert resp.status_code == 403


def test_remove_nonexistent_collaborator(client, bff_headers, registered_user):
    trip_id = _setup_trip_with_places(client, bff_headers)
    resp = client.delete(f"/internal/trips/{trip_id}/collaborators/999999", headers=bff_headers)
    assert resp.status_code == 404


# ─── Cross-user izolasyon (authorization) ────────────────────────────────────

def test_deleting_trip_cascades_shares_and_collaborators(client, bff_headers, registered_user):
    """Trip silindiğinde ilişkili share/collaborator kayıtları da temizlenmeli
    — silme sonrası yeniden oluşturulan aynı ID'li bir trip'e sızıntı olmasın."""
    trip_id = _setup_trip_with_places(client, bff_headers)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers
    ).json()
    collaborator_id, collaborator_headers = _second_user(client)

    resp = client.delete(f"/internal/trips/{trip_id}", headers=bff_headers)
    assert resp.status_code == 200

    # Token artık hiçbir şeye işaret etmiyor.
    assert client.get(f"/internal/shares/{share['token']}/preview").status_code == 404


def test_collaborator_of_one_trip_has_no_access_to_owners_other_trip(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Paylaşılan Mekan", 36.0, 29.0)])
    shared_trip_id = _make_trip(client, bff_headers, "Paylaşılan")

    _save_places(uid, [_loc("Özel Mekan", 37.0, 30.0)])
    private_trip_id = _make_trip(client, bff_headers, "Özel")

    share = client.post(
        f"/internal/trips/{shared_trip_id}/shares", json={"role": "editor"}, headers=bff_headers
    ).json()
    _, collaborator_headers = _second_user(client)
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=collaborator_headers)

    assert client.get(f"/internal/trips/{shared_trip_id}", headers=collaborator_headers).status_code == 200
    assert client.get(f"/internal/trips/{private_trip_id}", headers=collaborator_headers).status_code == 404
