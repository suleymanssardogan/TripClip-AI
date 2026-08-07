"""
Trip Optimizer entegrasyon testleri: uçtan uca API (optimize → persist →
list/get), yetkilendirme, ve request-hijyeni (dedup/validasyon) senaryoları.
"""
import uuid

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


def _make_trip(client, headers, place_ids=None, title: str = "Test Gezisi") -> int:
    if place_ids is None:
        place_ids = _library_place_ids(client, headers)
    resp = client.post("/internal/trips", json={"title": title, "place_ids": place_ids}, headers=headers)
    return resp.json()["id"]


def _second_user(client) -> tuple[int, dict]:
    email = f"u2_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post("/internal/auth/register", json={"email": email, "password": "P2_test!"})
    uid = resp.json()["user_id"]
    return uid, {"x-user-id": str(uid)}


def _setup_trip_with_places(client, headers, n: int = 2) -> tuple[int, list[int]]:
    uid = int(headers["x-user-id"])
    locs = [_loc(f"Mekan {i}", 36.0 + i * 0.1, 29.0 + i * 0.1) for i in range(n)]
    _save_places(uid, locs)
    place_ids = _library_place_ids(client, headers)
    trip_id = _make_trip(client, headers, place_ids)
    return trip_id, place_ids


# ─── Happy path ───────────────────────────────────────────────────────────────

def test_optimize_trip_happy_path(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=3)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trip_id"] == trip_id
    assert data["strategy_name"] == "greedy_distance"
    assert 0.0 <= data["optimization_score"] <= 100.0
    assert sum(len(d["stops"]) for d in data["days"]) == 3
    # Bugün Place'te opening_hours hiçbir pipeline tarafından doldurulmuyor —
    # bu yüzden bu uyarı her zaman beklenir (bkz. docs/trip-optimizer.md).
    assert any("Açılış saatleri bilinmiyor" in w for w in data["warnings"])


def test_optimize_trip_persists_and_is_listable(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=bff_headers,
    )
    itinerary_id = resp.json()["id"]

    list_resp = client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers)
    assert list_resp.status_code == 200
    ids = [it["id"] for it in list_resp.json()["itineraries"]]
    assert itinerary_id in ids

    get_resp = client.get(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == itinerary_id


def test_multiple_optimize_runs_do_not_overwrite_each_other(client, bff_headers):
    """Aynı trip için birden çok itinerary geçmişte kalmalı (bkz. TripItinerary
    docstring'i) — Trip Builder'ın TripStop'u gibi ezilmemeli."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    first = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()
    second = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()

    assert first["id"] != second["id"]
    list_resp = client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers)
    assert len(list_resp.json()["itineraries"]) == 2


def test_optimize_does_not_mutate_existing_trip_stops(client, bff_headers):
    """Trip Builder API'sini bozmama gereksinimi: optimize çağrısı Trip'in
    days/stops_count'unu değiştirmemeli."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    before = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()

    client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    )

    after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert before["days"] == after["days"]
    assert before["stops_count"] == after["stops_count"]


# ─── Edge case: empty trip ────────────────────────────────────────────────────

def test_optimize_with_no_selected_places_is_rejected(client, bff_headers):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": []},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


# ─── Edge case: duplicate places ──────────────────────────────────────────────

def test_duplicate_place_ids_are_deduped_with_warning(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    duplicated = place_ids + place_ids  # aynı id iki kez

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": duplicated},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert sum(len(d["stops"]) for d in data["days"]) == 1
    assert any("tekrarlı mekan seçimi kaldırıldı" in w for w in data["warnings"])


# ─── Edge case: multiple cities ───────────────────────────────────────────────

def test_multiple_cities_produces_long_segment_warning(client, bff_headers):
    uid = int(bff_headers["x-user-id"])
    locs = [
        _loc("Ayasofya", 41.0086, 28.9802, city="İstanbul"),
        _loc("Topkapı Sarayı", 41.0115, 28.9833, city="İstanbul"),
        _loc("Göreme Açık Hava Müzesi", 38.6425, 34.8288, city="Nevşehir"),
    ]
    _save_places(uid, locs)
    place_ids = _library_place_ids(client, bff_headers)
    trip_id = _make_trip(client, bff_headers, place_ids)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert any("uzun bir seyahat segmenti" in w for w in resp.json()["warnings"])


# ─── Edge case: unavailable metadata (opening hours) ──────────────────────────

def test_missing_opening_hours_is_surfaced_as_warning_not_error(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert any("Açılış saatleri bilinmiyor" in w for w in resp.json()["warnings"])


# ─── Validation ────────────────────────────────────────────────────────────────

def test_place_not_in_library_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids + [999999]},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_unknown_strategy_name_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "strategy": "quantum_teleportation"},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_invalid_time_format_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "preferred_start_time": "not-a-time"},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_end_time_before_start_time_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "preferred_start_time": "18:00", "preferred_end_time": "09:00"},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_invalid_start_date_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "start_date": "not-a-date"},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_duration_days_zero_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "duration_days": 0},
        headers=bff_headers,
    )
    assert resp.status_code == 400


# ─── Permission checks ─────────────────────────────────────────────────────────

def test_optimize_requires_auth(client):
    resp = client.post("/internal/trips/1/optimize", json={"selected_place_ids": [1]})
    assert resp.status_code == 401


def test_optimize_nonexistent_trip_is_404(client, bff_headers):
    resp = client.post(
        "/internal/trips/999999/optimize",
        json={"selected_place_ids": [1]},
        headers=bff_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRIP_NOT_FOUND"


def test_non_collaborator_cannot_optimize_someone_elses_trip(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _, outsider_headers = _second_user(client)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=outsider_headers,
    )
    # Trip Sharing'deki anti-enumeration deseniyle aynı: sahibi olmayan biri
    # için trip'in var olup olmadığı sızdırılmaz.
    assert resp.status_code == 404


def test_viewer_collaborator_cannot_optimize(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    viewer_uid, viewer_headers = _second_user(client)

    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers,
    ).json()
    client.post(
        "/internal/shares/accept", json={"token": share["token"]}, headers=viewer_headers,
    )

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_editor_collaborator_can_optimize(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    editor_uid, editor_headers = _second_user(client)

    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers,
    ).json()
    client.post(
        "/internal/shares/accept", json={"token": share["token"]}, headers=editor_headers,
    )

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=editor_headers,
    )
    assert resp.status_code == 200


def test_itinerary_not_visible_to_user_without_trip_access(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _, outsider_headers = _second_user(client)
    resp = client.get(f"/internal/itineraries/{itinerary_id}", headers=outsider_headers)
    assert resp.status_code == 404


def test_list_itineraries_requires_trip_access(client, bff_headers):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    _, outsider_headers = _second_user(client)

    resp = client.get(f"/internal/trips/{trip_id}/itineraries", headers=outsider_headers)
    assert resp.status_code == 404
