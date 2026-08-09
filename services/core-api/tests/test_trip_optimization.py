"""
Trip Optimizer entegrasyon testleri: uçtan uca API (optimize → persist →
list/get/apply), yetkilendirme, ve request-hijyeni (dedup/validasyon) senaryoları.
"""
import uuid
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


def _trip_stops_db(trip_id: int) -> list[tuple[int, int, int]]:
    """(place_id, day_index, order_index) — DB'den doğrudan, API'den değil."""
    from app.models.trip_stop import TripStop

    db = TestingSessionLocal()
    try:
        rows = db.query(TripStop).filter(TripStop.trip_id == trip_id).order_by(TripStop.order_index).all()
        return [(r.place_id, r.day_index, r.order_index) for r in rows]
    finally:
        db.close()


def _make_raw_itinerary(trip_id: int, stops: list[dict]) -> int:
    """optimize_trip API'sinin normalde önlediği durumları (boş/tekrarlı
    place_id) test edebilmek için TripItinerary/TripItineraryStop'u doğrudan
    DB'ye yazar — optimizer'ın kendi dedup/validasyonunu bilerek atlar."""
    from app.models.trip_itinerary import TripItinerary
    from app.models.trip_itinerary_stop import TripItineraryStop

    db = TestingSessionLocal()
    try:
        itinerary = TripItinerary(
            trip_id=trip_id, strategy_name="greedy_distance",
            optimization_score=90.0, total_distance_km=1.0, total_travel_time_minutes=5.0,
            warnings=[],
        )
        db.add(itinerary)
        db.flush()
        for s in stops:
            db.add(TripItineraryStop(
                itinerary_id=itinerary.id,
                place_id=s.get("place_id"),
                day_index=s.get("day_index", 0),
                order_index=s.get("order_index", 0),
                visit_duration_minutes=s.get("visit_duration_minutes", 60),
            ))
        db.commit()
        return itinerary.id
    finally:
        db.close()


def _delete_place_db(place_id: int) -> None:
    from app.models.place import Place

    db = TestingSessionLocal()
    try:
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
    finally:
        db.close()


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


def test_list_itineraries_includes_days_and_stops_count(client, bff_headers):
    """iOS Itinerary History listesi bunları full detail çekmeden gösterebilmeli."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    )

    list_resp = client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers)
    summary = list_resp.json()["itineraries"][0]
    assert summary["stops_count"] == 2
    assert summary["days_count"] == 1


def test_list_itineraries_newest_first(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    first = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()
    second = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()

    list_resp = client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers)
    ids_in_order = [it["id"] for it in list_resp.json()["itineraries"]]
    assert ids_in_order == [second["id"], first["id"]]


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


# ─── OR-Tools strategy selection (bkz. docs/trip-optimizer.md "Available strategies") ──

def test_optimize_trip_with_ortools_strategy_end_to_end(client, bff_headers):
    """`strategy: "ortools"` uçtan uca — API/servis katmanının hiçbir şey
    bilmeden yeni stratejiyi çözebildiğini kanıtlar (bu milestone'un asıl
    hedefi)."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=3)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "strategy": "ortools"},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trip_id"] == trip_id
    assert data["strategy_name"] == "ortools"
    assert 0.0 <= data["optimization_score"] <= 100.0
    assert sum(len(d["stops"]) for d in data["days"]) == 3


def test_ortools_itinerary_is_persisted_and_listable_alongside_greedy_ones(client, bff_headers):
    """İki farklı stratejiyle üretilmiş itinerary'ler aynı trip için yan
    yana var olabilir — apply/history akışları strateji-agnostik (bkz.
    docs/trip-optimizer.md "Apply semantics")."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    greedy_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "strategy": "greedy_distance"},
        headers=bff_headers,
    ).json()["id"]
    ortools_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "strategy": "ortools"},
        headers=bff_headers,
    ).json()["id"]

    listing = client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers).json()
    strategy_names = {item["id"]: item["strategy_name"] for item in listing["itineraries"]}
    assert strategy_names[greedy_id] == "greedy_distance"
    assert strategy_names[ortools_id] == "ortools"


def test_ortools_itinerary_can_be_applied_to_trip(client, bff_headers):
    """Apply akışı stratejiden bağımsız — bkz. sql_optimization_repository.
    apply_itinerary, strategy_name'i hiç bilmez."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "strategy": "ortools"},
        headers=bff_headers,
    ).json()["id"]

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json()["stops_count"] == 2
    assert len(_trip_stops_db(trip_id)) == 2


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


# ─── apply_itinerary ────────────────────────────────────────────────────────

def test_apply_itinerary_happy_path_replaces_trip_stops(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=3)
    itinerary = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()

    before = _trip_stops_db(trip_id)
    assert len(before) == 3  # create_trip zaten TripStop'ları doldurdu

    resp = client.post(f"/internal/itineraries/{itinerary['id']}/apply", headers=bff_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trip_id"] == trip_id
    assert data["itinerary_id"] == itinerary["id"]
    assert data["stops_count"] == 3
    assert len(data["stops"]) == 3
    assert "applied_at" in data

    after = _trip_stops_db(trip_id)
    assert len(after) == 3
    # Uygulanan itinerary'nin sırası TripStop'a birebir yansımalı.
    itinerary_order = [s["place_id"] for day in itinerary["days"] for s in day["stops"]]
    assert [pid for pid, _, _ in after] == itinerary_order


def test_apply_itinerary_editor_can_apply(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _, editor_headers = _second_user(client)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers,
    ).json()
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=editor_headers)

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=editor_headers)
    assert resp.status_code == 200


def test_apply_itinerary_viewer_forbidden(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _, viewer_headers = _second_user(client)
    share = client.post(
        f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers,
    ).json()
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=viewer_headers)

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=viewer_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_apply_itinerary_cross_user_rejected(client, bff_headers):
    """Trip'e HİÇBİR bağlantısı olmayan biri — anti-enumeration: 404, 403 değil."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _, outsider_headers = _second_user(client)
    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=outsider_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITINERARY_NOT_FOUND"


def test_apply_nonexistent_itinerary_404(client, bff_headers):
    resp = client.post("/internal/itineraries/999999/apply", headers=bff_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITINERARY_NOT_FOUND"


def test_apply_itinerary_requires_auth(client):
    resp = client.post("/internal/itineraries/1/apply")
    assert resp.status_code == 401


def test_apply_itinerary_with_deleted_place_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _delete_place_db(place_ids[0])  # ondelete=SET NULL -> TripItineraryStop.place_id NULL olur

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_apply_itinerary_empty_rejected(client, bff_headers):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = _make_raw_itinerary(trip_id, stops=[])

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_apply_itinerary_duplicate_places_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = _make_raw_itinerary(trip_id, stops=[
        {"place_id": place_ids[0], "order_index": 0},
        {"place_id": place_ids[0], "order_index": 1},  # aynı mekan iki kez
    ])

    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"


def test_apply_itinerary_atomic_rollback_leaves_existing_stops_untouched(client, bff_headers):
    """Reddedilen bir apply, mevcut TripStop'lara HİÇ dokunmamalı — kısmi
    güncelleme olmamalı (bkz. spesifikasyonun 'atomic' gereksinimi)."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    before = _trip_stops_db(trip_id)
    assert len(before) == 2

    bad_itinerary_id = _make_raw_itinerary(trip_id, stops=[])  # boş -> reddedilecek

    resp = client.post(f"/internal/itineraries/{bad_itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 400

    after = _trip_stops_db(trip_id)
    assert after == before  # birebir aynı — silinip yeniden eklenmedi


def test_apply_itinerary_can_be_applied_repeatedly(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    first = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert first.status_code == 200
    second = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)
    assert second.status_code == 200

    assert first.json()["stops"] == second.json()["stops"]
    assert len(_trip_stops_db(trip_id)) == 2  # tekrar uygulama durakları çoğaltmadı


def test_apply_itinerary_does_not_mutate_saved_itinerary(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    before = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()

    client.post(f"/internal/itineraries/{before['id']}/apply", headers=bff_headers)

    after = client.get(f"/internal/itineraries/{before['id']}", headers=bff_headers).json()
    assert after == before  # apply, itinerary'nin kendisini hiçbir şekilde değiştirmedi


def test_apply_itinerary_updates_trip_provenance_fields(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    trip_before = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_before["applied_itinerary_id"] is None
    assert trip_before["itinerary_applied_at"] is None

    client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)

    trip_after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_after["applied_itinerary_id"] == itinerary_id
    assert trip_after["itinerary_applied_at"] is not None


def test_apply_itinerary_fires_analytics_event(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)

    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["event"].value == "shared_trip_itinerary_applied"
    assert kwargs["trip_id"] == trip_id
    assert kwargs["kind"] == "trip"
    assert kwargs["user_id"] == int(bff_headers["x-user-id"])
    assert kwargs["metadata"]["itinerary_id"] == itinerary_id
    assert kwargs["metadata"]["stops_count"] == 2
