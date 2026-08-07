"""
Trip Builder testleri: Library'den seçilen mekanlardan TSP ile rota
oluşturma, sahiplik kontrolü, sıra düzenleme, silme.
"""
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
    """Video pipeline'ının çağırdığı gerçek kod yolu üzerinden Place'leri kütüphaneye ekler."""
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


# ─── Oluşturma ──────────────────────────────────────────────────────────────

def test_create_trip_from_library_places(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [
        _loc("Kaputaş Plajı", 36.1500, 29.4500),
        _loc("Saklıkent Kanyonu", 36.5167, 29.6167),
    ])
    place_ids = _library_place_ids(client, bff_headers)

    resp = client.post(
        "/internal/trips",
        json={"title": "Fethiye Turu", "place_ids": place_ids},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fethiye Turu"
    assert data["stops_count"] == 2
    assert len(data["days"]) == 1
    assert data["total_distance_km"] > 0
    # TSP rotası girdi sırasını korumak zorunda değil, ama iki mekan de bulunmalı
    routed_ids = {stop["place_id"] for stop in data["days"][0]}
    assert routed_ids == set(place_ids)


def test_create_trip_single_place_has_zero_distance(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Tek Mekan", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)

    resp = client.post(
        "/internal/trips",
        json={"title": "Tek Duraklı", "place_ids": place_ids},
        headers=bff_headers,
    )
    data = resp.json()
    assert data["stops_count"] == 1
    assert data["total_distance_km"] == 0


def test_create_trip_empty_places_rejected(client, bff_headers):
    resp = client.post(
        "/internal/trips",
        json={"title": "Boş", "place_ids": []},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRIP_PLACES"


def test_create_trip_duplicate_place_ids_rejected(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Mekan", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)

    resp = client.post(
        "/internal/trips",
        json={"title": "Tekrarlı", "place_ids": place_ids * 2},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRIP_PLACES"


def test_create_trip_with_foreign_place_id_rejected(client, bff_headers, registered_user):
    """Başka bir kullanıcının kütüphanesindeki mekan Trip'e eklenememeli."""
    import uuid
    from app.main import app
    from fastapi.testclient import TestClient

    uid_a = registered_user["user_id"]
    _save_places(uid_a, [_loc("A'nın Mekanı", 36.0, 29.0)])
    place_ids_a = _library_place_ids(client, bff_headers)

    with TestClient(app) as c2:
        email_b = f"b_{uuid.uuid4().hex[:6]}@test.com"
        rb = c2.post("/internal/auth/register", json={"email": email_b, "password": "P2_test!"})
        uid_b = rb.json()["user_id"]
        headers_b = {"x-user-id": str(uid_b)}

        resp = c2.post(
            "/internal/trips",
            json={"title": "Sızıntı Denemesi", "place_ids": place_ids_a},
            headers=headers_b,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_TRIP_PLACES"


def test_create_trip_requires_auth(client):
    resp = client.post("/internal/trips", json={"title": "X", "place_ids": [1]})
    assert resp.status_code == 401


# ─── Okuma ──────────────────────────────────────────────────────────────────

def test_get_trip_not_found(client, bff_headers):
    resp = client.get("/internal/trips/999999", headers=bff_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRIP_NOT_FOUND"


def test_get_trip_wrong_owner_is_not_found(client, bff_headers, registered_user):
    import uuid
    from app.main import app
    from fastapi.testclient import TestClient

    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Gizli Mekan", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Gizli", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    with TestClient(app) as c2:
        email_b = f"b_{uuid.uuid4().hex[:6]}@test.com"
        rb = c2.post("/internal/auth/register", json={"email": email_b, "password": "P2_test!"})
        headers_b = {"x-user-id": str(rb.json()["user_id"])}
        resp = c2.get(f"/internal/trips/{trip_id}", headers=headers_b)
        assert resp.status_code == 404


def test_list_trips(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Liste Mekanı", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)
    client.post("/internal/trips", json={"title": "İlk Gezi", "place_ids": place_ids}, headers=bff_headers)

    resp = client.get("/internal/trips", headers=bff_headers)
    assert resp.status_code == 200
    trips = resp.json()["trips"]
    assert len(trips) == 1
    assert trips[0]["title"] == "İlk Gezi"
    assert trips[0]["stops_count"] == 1


# ─── Sıra düzenleme ─────────────────────────────────────────────────────────

def test_update_stop_order(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [
        _loc("Birinci", 36.0, 29.0),
        _loc("İkinci", 36.1, 29.1),
    ])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Sıra Testi", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    reversed_ids = list(reversed(place_ids))
    resp = client.patch(
        f"/internal/trips/{trip_id}/order",
        json={"order": [reversed_ids]},
        headers=bff_headers,
    )
    assert resp.status_code == 200

    detail = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert [s["place_id"] for s in detail["days"][0]] == reversed_ids


def test_update_stop_order_can_remove_a_stop(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [
        _loc("Kalan", 36.0, 29.0),
        _loc("Silinen", 36.1, 29.1),
    ])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Silme Testi", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    keep_id = place_ids[0]
    resp = client.patch(
        f"/internal/trips/{trip_id}/order",
        json={"order": [[keep_id]]},
        headers=bff_headers,
    )
    assert resp.status_code == 200

    detail = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert detail["stops_count"] == 1
    assert detail["days"][0][0]["place_id"] == keep_id


def test_update_stop_order_unknown_place_rejected(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Mekan", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Geçersiz", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    resp = client.patch(
        f"/internal/trips/{trip_id}/order",
        json={"order": [[999999]]},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRIP_STOP_ORDER"


def test_update_stop_order_duplicate_rejected(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Mekan", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Tekrar", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    resp = client.patch(
        f"/internal/trips/{trip_id}/order",
        json={"order": [place_ids, place_ids]},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TRIP_STOP_ORDER"


# ─── Silme ──────────────────────────────────────────────────────────────────

def test_delete_trip(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    _save_places(uid, [_loc("Silinecek Gezi Mekanı", 36.0, 29.0)])
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = client.post(
        "/internal/trips", json={"title": "Silinecek", "place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    resp = client.delete(f"/internal/trips/{trip_id}", headers=bff_headers)
    assert resp.status_code == 200

    resp2 = client.get(f"/internal/trips/{trip_id}", headers=bff_headers)
    assert resp2.status_code == 404


def test_delete_trip_not_found(client, bff_headers):
    resp = client.delete("/internal/trips/999999", headers=bff_headers)
    assert resp.status_code == 404
