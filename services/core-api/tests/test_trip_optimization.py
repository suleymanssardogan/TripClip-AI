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


def test_equal_start_and_end_time_is_rejected(client, bff_headers):
    """Yalnızca EŞİT değerler hâlâ reddedilir (bkz. "Overnight Time Ranges" —
    mevcut sözleşmenin korunan tek kısmı; `end < start` artık overnight bir
    pencere olarak KABUL edilir, bkz. aşağıdaki
    test_overnight_preferred_time_range_is_accepted)."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "preferred_start_time": "12:00", "preferred_end_time": "12:00"},
        headers=bff_headers,
    )
    assert resp.status_code == 400


def test_overnight_preferred_time_range_is_accepted(client, bff_headers):
    """`preferred_end_time < preferred_start_time` ARTIK geçerli bir
    overnight planlama penceresi olarak kabul edilir — 400 DEĞİL, itinerary
    normal şekilde üretilir (bkz. "Overnight Time Ranges")."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "preferred_start_time": "18:00", "preferred_end_time": "01:00"},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["days"][0]["stops"][0]["arrival_time"] == "18:00"


def test_invalid_start_date_is_rejected(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "start_date": "not-a-date"},
        headers=bff_headers,
    )
    assert resp.status_code == 400


# ─── Trip Planning Date ─────────────────────────────────────────────────────
#
# `start_date` already existed in OptimizeTripRequest/OptimizationConstraints
# and both strategies already computed OptimizedDay.date from it — this
# milestone's only backend change is that ItineraryDayResponse/get_itinerary
# now actually SURFACE that already-computed value (bkz.
# docs/trip-optimizer.md "Trip Planning Date").

def test_optimize_without_start_date_leaves_day_date_null(client, bff_headers):
    """Geriye dönük uyumluluk: start_date hiç gönderilmezse (bu milestone'dan
    önceki her istek gibi) her günün date'i None kalmalı."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["days"][0]["date"] is None


def test_optimize_with_start_date_derives_calendar_date_per_day(client, bff_headers):
    """Gün 1 = start_date, Gün 2 = start_date + 1 takvim günü, ... — 24 saat
    eklemeyle DEĞİL, saf takvim günü aritmetiğiyle (bkz. _date_for,
    greedy_distance_strategy.py, saat dilimi/saat bileşeni YOK).

    İki durağı ayrı günlere zorlamak için dar bir preferred_start_time/
    end_time penceresi kullanılıyor (60 dakikalık varsayılan ziyaret süresi
    tam pencereyi dolduruyor, bkz. test_optimization_strategy.py'nin AYNI
    tekniği) — mesafeye değil, zaman bütçesine dayanan deterministik bir
    gün bölünmesi.
    """
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)

    resp = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={
            "selected_place_ids": place_ids,
            "start_date": "2026-09-01",
            "preferred_start_time": "09:00",
            "preferred_end_time": "10:00",
        },
        headers=bff_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    days_by_index = {d["day_index"]: d["date"] for d in data["days"]}
    assert days_by_index == {0: "2026-09-01", 1: "2026-09-02"}


def test_saved_itinerary_preserves_start_date_when_reloaded_from_history(client, bff_headers):
    """Itinerary History'den bir kaydı yeniden yüklemek (Req 8) — optimizer
    TEKRAR ÇALIŞTIRILMADAN — planlama tarihini korumalı. `TripItineraryStop`
    tarih saklamıyor; bu, `TripItinerary.params`'ta saklanan `start_date`'in
    her GET çağrısında doğru biçimde yeniden türetildiğini kanıtlar."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    created = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids, "start_date": "2026-09-01"},
        headers=bff_headers,
    ).json()

    reloaded = client.get(f"/internal/itineraries/{created['id']}", headers=bff_headers)
    assert reloaded.status_code == 200
    assert reloaded.json()["days"][0]["date"] == "2026-09-01"


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


# ─── delete_itinerary (Milestone 19 — Delete Saved Itinerary from History) ─────

def _itinerary_stop_ids_db(itinerary_id: int) -> list[int]:
    from app.models.trip_itinerary_stop import TripItineraryStop

    db = TestingSessionLocal()
    try:
        rows = db.query(TripItineraryStop.id).filter(TripItineraryStop.itinerary_id == itinerary_id).all()
        return [r[0] for r in rows]
    finally:
        db.close()


def _itinerary_exists_db(itinerary_id: int) -> bool:
    from app.models.trip_itinerary import TripItinerary

    db = TestingSessionLocal()
    try:
        return db.query(TripItinerary).filter(TripItinerary.id == itinerary_id).first() is not None
    finally:
        db.close()


def _place_ids_db(place_ids: list[int]) -> list[int]:
    from app.models.place import Place

    db = TestingSessionLocal()
    try:
        rows = db.query(Place.id).filter(Place.id.in_(place_ids)).all()
        return [r[0] for r in rows]
    finally:
        db.close()


def test_delete_itinerary_happy_path(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    resp = client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert not _itinerary_exists_db(itinerary_id)


def test_delete_itinerary_removes_it_from_list(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    ids = [it["id"] for it in client.get(f"/internal/trips/{trip_id}/itineraries", headers=bff_headers).json()["itineraries"]]
    assert itinerary_id not in ids


def test_delete_itinerary_removes_child_stop_records(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=3)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    assert len(_itinerary_stop_ids_db(itinerary_id)) == 3

    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    assert _itinerary_stop_ids_db(itinerary_id) == []


def test_delete_itinerary_does_not_touch_trip_stops(client, bff_headers):
    """TripStop (Trip'in kanonik durak listesi) itinerary silme işleminden
    TAMAMEN bağımsız — bkz. TripItinerary docstring'i."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    before = _trip_stops_db(trip_id)

    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    assert _trip_stops_db(trip_id) == before


def test_delete_itinerary_does_not_touch_places(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    assert sorted(_place_ids_db(place_ids)) == sorted(place_ids)


def test_delete_itinerary_does_not_affect_other_itineraries_of_same_trip(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    first = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    second = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    client.delete(f"/internal/itineraries/{first}", headers=bff_headers)

    resp = client.get(f"/internal/itineraries/{second}", headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == second
    assert len(_itinerary_stop_ids_db(second)) == 2


def test_delete_nonexistent_itinerary_404(client, bff_headers):
    resp = client.delete("/internal/itineraries/999999", headers=bff_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITINERARY_NOT_FOUND"


def test_delete_itinerary_cross_user_rejected_as_404(client, bff_headers):
    """Trip'e HİÇBİR bağlantısı olmayan biri — anti-enumeration: 404."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]

    _, outsider_headers = _second_user(client)
    resp = client.delete(f"/internal/itineraries/{itinerary_id}", headers=outsider_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITINERARY_NOT_FOUND"
    assert _itinerary_exists_db(itinerary_id)  # dokunulmadı


def test_delete_itinerary_viewer_forbidden_as_404(client, bff_headers):
    """Delete'in anti-enumeration'ı apply'dan daha SIKI — viewer (trip'e
    erişimi olan ama owner/editor olmayan biri) için de PERMISSION_DENIED
    (403) değil, ITINERARY_NOT_FOUND (404) dönülmeli (bkz. milestone spec'inin
    kendi 'unauthorized/non-owner/non-editor → 404' gereksinimi — bu,
    apply_itinerary'nin 403 döndüğü aynı senaryodan KASITLI olarak farklı)."""
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

    resp = client.delete(f"/internal/itineraries/{itinerary_id}", headers=viewer_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITINERARY_NOT_FOUND"
    assert _itinerary_exists_db(itinerary_id)  # dokunulmadı — reddedilen istek hiçbir şeyi mutasyona uğratmadı


def test_delete_itinerary_editor_can_delete(client, bff_headers):
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

    resp = client.delete(f"/internal/itineraries/{itinerary_id}", headers=editor_headers)
    assert resp.status_code == 200
    assert not _itinerary_exists_db(itinerary_id)


def test_delete_itinerary_requires_auth(client):
    resp = client.delete("/internal/itineraries/1")
    assert resp.status_code == 401


def test_delete_applied_itinerary_clears_trip_reference(client, bff_headers):
    """Trip.applied_itinerary_id bu itinerary'e işaret ediyorsa, silme
    işlemi bunu güvenle temizlemeli — dangling FK bırakmamalı."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=bff_headers)

    trip_before = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_before["applied_itinerary_id"] == itinerary_id

    resp = client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)
    assert resp.status_code == 200

    trip_after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_after["applied_itinerary_id"] is None
    assert trip_after["itinerary_applied_at"] is None
    # Uygulanmış kanonik TripStop'lar (itinerary'nin KENDİSİ değil, onun
    # zaten kopyaladığı Trip'in durakları) silme işleminden ETKİLENMEMELİ.
    assert len(_trip_stops_db(trip_id)) == 1


def test_delete_non_applied_itinerary_does_not_affect_applied_itinerary_id(client, bff_headers):
    """B uygulanmışken A'yı silmek, Trip.applied_itinerary_id'nin B'ye
    işaret etmeye devam etmesini ETKİLEMEMELİ."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    a = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    b = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=bff_headers,
    ).json()["id"]
    client.post(f"/internal/itineraries/{b}/apply", headers=bff_headers)

    client.delete(f"/internal/itineraries/{a}", headers=bff_headers)

    trip_after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_after["applied_itinerary_id"] == b


# ─── Apply History & Undo (Milestone 20) ───────────────────────────────────────

def _apply_history_db(trip_id: int) -> list:
    """(id, itinerary_id, previous_itinerary_id, is_undo) — DB'den doğrudan,
    en yeniden eskiye — API'den değil."""
    from app.models.trip_itinerary_apply_history import TripItineraryApplyHistory

    db = TestingSessionLocal()
    try:
        rows = (
            db.query(TripItineraryApplyHistory)
            .filter(TripItineraryApplyHistory.trip_id == trip_id)
            .order_by(TripItineraryApplyHistory.id.desc())
            .all()
        )
        return [
            (r.id, r.itinerary_id, r.previous_itinerary_id, r.is_undo, r.previous_stops)
            for r in rows
        ]
    finally:
        db.close()


def _apply(client, headers, trip_id: int, place_ids: list) -> int:
    """Optimize + apply tek adımda — itinerary_id döner."""
    itinerary_id = client.post(
        f"/internal/trips/{trip_id}/optimize",
        json={"selected_place_ids": place_ids}, headers=headers,
    ).json()["id"]
    resp = client.post(f"/internal/itineraries/{itinerary_id}/apply", headers=headers)
    assert resp.status_code == 200
    return itinerary_id


def test_apply_history_created_on_successful_apply(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    itinerary_id = _apply(client, bff_headers, trip_id, place_ids)

    resp = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["itinerary_id"] == itinerary_id
    assert entries[0]["is_undo"] is False
    assert entries[0]["is_undoable"] is True
    assert entries[0]["actor_user_id"] == int(bff_headers["x-user-id"])


def test_apply_history_ordering_newest_first(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    a = _apply(client, bff_headers, trip_id, place_ids)
    b = _apply(client, bff_headers, trip_id, place_ids)

    entries = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    assert [e["itinerary_id"] for e in entries] == [b, a]


def test_apply_history_only_latest_is_undoable(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, place_ids)

    entries = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    assert entries[0]["is_undoable"] is True   # B (en yeni)
    assert entries[1]["is_undoable"] is False  # A


def test_apply_history_records_complete_previous_stop_snapshot(client, bff_headers):
    """Apply'dan HEMEN ÖNCEki TripStop durumu (trip oluşturulurken doldurulan
    ORİJİNAL duraklar) tam olarak snapshot'a yazılmalı — yalnızca place_id
    değil, day_index/order_index de."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    original_stops = sorted(_trip_stops_db(trip_id))  # apply'dan ÖNCEki durum

    _apply(client, bff_headers, trip_id, place_ids)

    history = _apply_history_db(trip_id)
    assert len(history) == 1
    _, _, previous_itinerary_id, is_undo, previous_stops = history[0]
    assert previous_itinerary_id is None  # ilk apply — daha önce hiç itinerary uygulanmamıştı
    assert is_undo is False
    snapshot_tuples = sorted((s["place_id"], s["day_index"], s["order_index"]) for s in previous_stops)
    assert snapshot_tuples == original_stops


def test_undo_restores_exact_previous_tripstop_state(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=3)
    _apply(client, bff_headers, trip_id, place_ids)
    stops_after_a = sorted(_trip_stops_db(trip_id))
    _apply(client, bff_headers, trip_id, [place_ids[0], place_ids[1]])
    stops_after_b = sorted(_trip_stops_db(trip_id))
    assert stops_after_a != stops_after_b  # gerçekten farklı bir durum

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]

    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo",
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert sorted(_trip_stops_db(trip_id)) == stops_after_a


def test_undo_updates_applied_itinerary_id(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    a = _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, place_ids)  # B — aynı itinerary ID farklı olsun diye yeniden optimize

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo",
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["itinerary_id"] == a

    trip_after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_after["applied_itinerary_id"] == a
    assert trip_after["itinerary_applied_at"] is not None


def test_undo_stale_conflict_rejected(client, bff_headers):
    """Apply A, Apply B, A'nın (artık en son OLMAYAN) kaydını geri almaya
    çalışmak 409 dönmeli — TripStops DEĞİŞMEMELİ (hâlâ B)."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, [place_ids[0]])
    stops_after_b = sorted(_trip_stops_db(trip_id))

    entries = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    stale_history_id = entries[1]["id"]  # A'nın kaydı, artık en son değil
    assert entries[1]["is_undoable"] is False

    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{stale_history_id}/undo",
        headers=bff_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "STALE_UNDO"
    assert sorted(_trip_stops_db(trip_id)) == stops_after_b  # dokunulmadı


def test_undo_creates_new_history_entry(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, [place_ids[0]])

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo", headers=bff_headers)

    entries = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    assert len(entries) == 3
    assert entries[0]["is_undo"] is True
    assert entries[0]["is_undoable"] is True
    assert entries[1]["is_undoable"] is False  # eski latest artık undoable değil


def test_undo_of_undo_behaves_as_redo(client, bff_headers):
    """Uniform log tasarımı: bir undo kaydının KENDİSİ de (en sonuncuysa)
    geri alınabilir — bu doğal bir 'yinele' (redo) sonucu üretir, özel bir
    durum GEREKTİRMEZ (bkz. docs/trip-optimizer.md 'Apply History & Undo')."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, [place_ids[0]])
    stops_after_b = sorted(_trip_stops_db(trip_id))

    first_undo_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/{first_undo_id}/undo", headers=bff_headers)

    second_undo_target_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{second_undo_target_id}/undo",
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert sorted(_trip_stops_db(trip_id)) == stops_after_b  # B'ye geri dönüldü ("redo")


def test_undo_never_mutates_saved_itinerary(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    a = _apply(client, bff_headers, trip_id, place_ids)
    before = client.get(f"/internal/itineraries/{a}", headers=bff_headers).json()
    _apply(client, bff_headers, trip_id, [place_ids[0]])

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo", headers=bff_headers)

    after = client.get(f"/internal/itineraries/{a}", headers=bff_headers).json()
    assert after == before


def test_delete_itinerary_does_not_destroy_apply_history(client, bff_headers):
    """bkz. 'Important deletion semantics' — itinerary silinse bile apply
    geçmişi kalıcı kalmalı, yalnızca itinerary_id NULL'a düşer."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = _apply(client, bff_headers, trip_id, place_ids)

    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    resp = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers)
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["itinerary_id"] is None  # ondelete=SET NULL
    assert entries[0]["is_undoable"] is True   # kayıt hâlâ geçerli/en son


def test_apply_history_permission_owner_can_view_and_undo(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)
    assert client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).status_code == 200


def test_apply_history_editor_can_undo(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, place_ids)

    _, editor_headers = _second_user(client)
    share = client.post(f"/internal/trips/{trip_id}/shares", json={"role": "editor"}, headers=bff_headers).json()
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=editor_headers)

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=editor_headers
    ).json()["entries"][0]["id"]
    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo", headers=editor_headers,
    )
    assert resp.status_code == 200


def test_apply_history_viewer_can_view_but_not_undo(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)

    _, viewer_headers = _second_user(client)
    share = client.post(f"/internal/trips/{trip_id}/shares", json={"role": "viewer"}, headers=bff_headers).json()
    client.post("/internal/shares/accept", json={"token": share["token"]}, headers=viewer_headers)

    list_resp = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=viewer_headers)
    assert list_resp.status_code == 200

    history_id = list_resp.json()["entries"][0]["id"]
    undo_resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo", headers=viewer_headers,
    )
    assert undo_resp.status_code == 403
    assert undo_resp.json()["error"]["code"] == "PERMISSION_DENIED"


def test_apply_history_outsider_gets_404_for_view_and_undo(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)
    _, outsider_headers = _second_user(client)

    assert client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=outsider_headers
    ).status_code == 404

    history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo", headers=outsider_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRIP_NOT_FOUND"


def test_list_apply_history_requires_auth(client):
    resp = client.get("/internal/trips/1/itinerary-apply-history")
    assert resp.status_code == 401


def test_undo_requires_auth(client):
    resp = client.post("/internal/trips/1/itinerary-apply-history/1/undo")
    assert resp.status_code == 401


def test_undo_nonexistent_trip_404(client, bff_headers):
    resp = client.post("/internal/trips/999999/itinerary-apply-history/1/undo", headers=bff_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRIP_NOT_FOUND"


def test_undo_nonexistent_history_404(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)

    resp = client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/999999/undo", headers=bff_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "APPLY_HISTORY_NOT_FOUND"


def test_undo_history_belonging_to_different_trip_is_404(client, bff_headers):
    trip_a, places_a = _setup_trip_with_places(client, bff_headers, n=1)
    trip_b, places_b = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_a, places_a)
    history_id_for_a = client.get(
        f"/internal/trips/{trip_a}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]

    # trip_b altında, trip_a'nın history_id'siyle geri almaya çalış.
    resp = client.post(
        f"/internal/trips/{trip_b}/itinerary-apply-history/{history_id_for_a}/undo", headers=bff_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "APPLY_HISTORY_NOT_FOUND"


def test_apply_failure_creates_no_history_record(client, bff_headers):
    trip_id, _ = _setup_trip_with_places(client, bff_headers, n=1)
    empty_itinerary_id = _make_raw_itinerary(trip_id, stops=[])

    resp = client.post(f"/internal/itineraries/{empty_itinerary_id}/apply", headers=bff_headers)
    assert resp.status_code == 400
    assert _apply_history_db(trip_id) == []


def test_undo_failure_leaves_tripstops_and_history_unchanged(client, bff_headers):
    """Restore edilecek anlık görüntüdeki bir Place sonradan silinmişse undo
    400 dönmeli — TripStops VE apply history hiç değişmemeli (atomiklik)."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    _apply(client, bff_headers, trip_id, place_ids)          # A — previous_stops'u ORİJİNAL duraklar
    _apply(client, bff_headers, trip_id, [place_ids[0]])      # B — en son, undo hedefi

    _delete_place_db(place_ids[1])  # A'nın orijinal previous_stops'unda olan bir mekan siliniyor

    history_before = _apply_history_db(trip_id)
    stops_before = sorted(_trip_stops_db(trip_id))

    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    resp = client.post(
        f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo", headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_OPTIMIZATION_REQUEST"

    assert sorted(_trip_stops_db(trip_id)) == stops_before
    assert _apply_history_db(trip_id) == history_before


def test_undo_first_apply_clears_applied_itinerary_id(client, bff_headers):
    """İlk (ve tek) apply'ı geri almak, trip'i hiçbir itinerary
    uygulanmamış gibi (applied_itinerary_id=None) bırakmalı — 'Do not
    guess' gereksinimi: restore edilen durum itinerary-kökenli DEĞİL."""
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=2)
    original_stops = sorted(_trip_stops_db(trip_id))
    _apply(client, bff_headers, trip_id, [place_ids[0]])

    history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]
    resp = client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo", headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json()["itinerary_id"] is None

    trip_after = client.get(f"/internal/trips/{trip_id}", headers=bff_headers).json()
    assert trip_after["applied_itinerary_id"] is None
    assert trip_after["itinerary_applied_at"] is None
    assert sorted(_trip_stops_db(trip_id)) == original_stops


def test_apply_history_trip_isolation(client, bff_headers):
    trip_a, places_a = _setup_trip_with_places(client, bff_headers, n=1)
    trip_b, places_b = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_a, places_a)
    _apply(client, bff_headers, trip_b, places_b)
    _apply(client, bff_headers, trip_b, places_b)

    entries_a = client.get(f"/internal/trips/{trip_a}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    entries_b = client.get(f"/internal/trips/{trip_b}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    assert len(entries_a) == 1
    assert len(entries_b) == 2


def test_apply_history_survives_deleted_itinerary_shows_itinerary_created_at_null(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    itinerary_id = _apply(client, bff_headers, trip_id, place_ids)
    client.delete(f"/internal/itineraries/{itinerary_id}", headers=bff_headers)

    entries = client.get(f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers).json()["entries"]
    assert entries[0]["itinerary_created_at"] is None


def test_undo_fires_apply_undone_analytics_event(client, bff_headers):
    trip_id, place_ids = _setup_trip_with_places(client, bff_headers, n=1)
    _apply(client, bff_headers, trip_id, place_ids)
    _apply(client, bff_headers, trip_id, place_ids)
    latest_history_id = client.get(
        f"/internal/trips/{trip_id}/itinerary-apply-history", headers=bff_headers
    ).json()["entries"][0]["id"]

    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        client.post(f"/internal/trips/{trip_id}/itinerary-apply-history/{latest_history_id}/undo", headers=bff_headers)

    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["event"].value == "shared_trip_itinerary_apply_undone"
    assert kwargs["trip_id"] == trip_id
    assert kwargs["kind"] == "trip"
