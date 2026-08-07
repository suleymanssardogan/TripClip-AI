"""
Place kütüphanesi testleri: videolar-arası tekilleştirme, kayıt-üzerine-
senkronizasyon (save_results hook), kütüphane endpoint'i.
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


def _save_results(video_id: int, locations: list) -> None:
    """VideoService'in çağırdığı gerçek kod yolu — Celery task'ların yaptığı gibi."""
    from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository

    db = TestingSessionLocal()
    try:
        repo = SqlVideoRepository(db)
        repo.save_results(video_id, {"deduplicated_locations": locations})
    finally:
        db.close()


def _loc(name: str, lat: float, lng: float, city: str = "Antalya", category: str = None) -> dict:
    """
    Nominatim'in gerçek `deduplicated_locations` şeklini taklit eder — city
    üst seviyede DEĞİL, `place_data.address_details.city/town/province/state`
    içinde gelir (bkz. SqlPlaceRepository._extract_city). `category`,
    PlacesService._categorize'ın ürettiği sabit taksonomi etiketi.
    """
    place_data = {
        "name": name,
        "address": f"{name}, {city}",
        "location": {"lat": lat, "lng": lng},
        "address_details": {"city": city},
    }
    if category:
        place_data["category"] = category
    return {"original_name": name, "place_data": place_data}


# ─── Senkronizasyon (save_results hook) ────────────────────────────────────

def test_save_results_populates_library(client, bff_headers, registered_user):
    """Video tamamlanınca kütüphane otomatik dolmalı — backfill'e gerek kalmadan."""
    uid = registered_user["user_id"]
    vid = _make_video(uid)
    _save_results(vid, [_loc("Kaputaş Plajı", 36.1500, 29.4500)])

    resp = client.get("/internal/places", headers=bff_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["places"][0]["name"] == "Kaputaş Plajı"
    assert data["places"][0]["save_count"] == 1


def test_two_videos_same_place_merge_into_one(client, bff_headers, registered_user):
    """Aynı mekan iki farklı videodan çıkarsa kütüphanede TEK satır olmalı."""
    uid = registered_user["user_id"]
    v1 = _make_video(uid, "a.mp4")
    v2 = _make_video(uid, "b.mp4")

    _save_results(v1, [_loc("Kaş Halk Plajı", 36.2000, 29.6400)])
    # Aynı isim, birkaç metre kaymış koordinat (gerçek geocoder gürültüsü).
    _save_results(v2, [_loc("Kaş Halk Plajı", 36.2003, 29.6402)])

    data = client.get("/internal/places", headers=bff_headers).json()
    assert data["total"] == 1
    assert data["places"][0]["save_count"] == 1  # aynı kullanıcı → tekrar sayılmaz


def test_two_distinct_nearby_places_stay_separate(client, bff_headers, registered_user):
    """Farklı isimli iki mekan aynı şehirde olsa bile ayrı kalmalı."""
    uid = registered_user["user_id"]
    vid = _make_video(uid)
    _save_results(vid, [
        _loc("Güllüoğlu Baklava", 36.10, 29.60),
        _loc("Elmacı Pazarı", 36.10, 29.60),
    ])

    data = client.get("/internal/places", headers=bff_headers).json()
    assert data["total"] == 2


def test_two_users_saving_same_place_share_one_place_row(client, registered_user):
    """Farklı kullanıcılar aynı mekanı kaydederse Place paylaşılır, save_count 2 olur."""
    import uuid
    from app.core.database import get_db
    from app.main import app

    uid_a = registered_user["user_id"]
    v1 = _make_video(uid_a)
    _save_results(v1, [_loc("Düden Şelalesi", 36.90, 30.70)])

    # İkinci kullanıcı
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        email_b = f"b_{uuid.uuid4().hex[:6]}@test.com"
        rb = client.post("/internal/auth/register", json={"email": email_b, "password": "P2_test!"})
        uid_b = rb.json()["user_id"]
        v2 = _make_video(uid_b)
        _save_results(v2, [_loc("Düden Şelalesi", 36.9001, 30.7001)])

        data_a = client.get("/internal/places", headers={"x-user-id": str(uid_a)}).json()
        data_b = client.get("/internal/places", headers={"x-user-id": str(uid_b)}).json()

    assert data_a["total"] == 1
    assert data_b["total"] == 1
    # İki kullanıcı da kendi kütüphanesinde görüyor, ve save_count paylaşılan
    # Place üzerinde 2'ye çıkmış olmalı.
    assert data_a["places"][0]["save_count"] == 2
    assert data_b["places"][0]["save_count"] == 2


def test_video_without_owner_is_skipped_safely(registered_user):
    """user_id=None olan video (edge case) senkronizasyonu patlatmamalı."""
    vid = _make_video(user_id=None)
    _save_results(vid, [_loc("Sahipsiz Mekan", 36.0, 30.0)])  # exception fırlatmamalı


# ─── Kütüphane endpoint'i ───────────────────────────────────────────────────

def test_library_requires_auth(client):
    resp = client.get("/internal/places")
    assert resp.status_code == 401


def test_library_empty_for_new_user(client, bff_headers):
    resp = client.get("/internal/places", headers=bff_headers)
    assert resp.status_code == 200
    assert resp.json() == {"places": [], "total": 0}


def test_library_city_filter(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    vid = _make_video(uid)
    _save_results(vid, [
        _loc("Kleopatra Plajı", 36.88, 30.70, city="Antalya"),
        _loc("Kız Kulesi", 41.02, 29.00, city="İstanbul"),
    ])

    resp = client.get("/internal/places?city=Antalya", headers=bff_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["places"][0]["name"] == "Kleopatra Plajı"


def test_library_search_query(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    vid = _make_video(uid)
    _save_results(vid, [_loc("Mermerli Plajı", 36.19, 29.63)])

    resp = client.get("/internal/places?q=mermerli", headers=bff_headers)
    assert resp.json()["total"] == 1

    resp2 = client.get("/internal/places?q=nomatch", headers=bff_headers)
    assert resp2.json()["total"] == 0


def test_library_limit_is_capped(client, bff_headers):
    resp = client.get("/internal/places?limit=9999", headers=bff_headers)
    assert resp.status_code == 422


# ─── City çıkarımı (address_details) ────────────────────────────────────────
#
# Gerçek Nominatim çıktısında city üst seviyede yok — `place_data.address_details`
# içinde city/town/province/state gibi anahtarlardan biri olarak geliyor.
# Bu testler gerçek üretim verisinden (docker exec ile doğrulanmış) alınan şekli
# kullanıyor, önceki (hatalı varsayılan) test fixture'ının aksine.

def _loc_with_address_details(name: str, lat: float, lng: float, address_details: dict) -> dict:
    return {
        "original_name": name,
        "place_data": {
            "name": name,
            "location": {"lat": lat, "lng": lng},
            "address_details": address_details,
        },
    }


def test_city_extracted_from_address_details(client, bff_headers, registered_user):
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [
        _loc_with_address_details("Halfeti", 37.23, 37.94, {"town": "Halfeti", "province": "Şanlıurfa"}),
    ])
    data = client.get("/internal/places", headers=bff_headers).json()
    # "town" > "province" önceliğine göre "Halfeti" değil "Şanlıurfa" seçilmemeli —
    # city_hint önceliği city > town > province > state, city yok → town kazanır.
    assert data["places"][0]["city"] == "Halfeti"


def test_city_extraction_missing_address_details_stays_none(client, bff_headers, registered_user):
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [_loc_with_address_details("Bilinmeyen Yer", 10.0, 10.0, {})])
    data = client.get("/internal/places", headers=bff_headers).json()
    assert data["places"][0]["city"] is None


def test_existing_null_city_place_gets_enriched_by_later_video(client, bff_headers, registered_user):
    """Backfill'i tekrar çalıştırmanın (ya da yeni bir videonun) eski, city'si
    boş bir Place'i zenginleştirebildiğini doğrular — veri kaybını önlemek için
    tam yeniden-oluşturma gerekmiyor."""
    uid = registered_user["user_id"]

    v1 = _make_video(uid, "no_city.mp4")
    _save_results(v1, [_loc_with_address_details("Kale", 38.0, 38.0, {})])

    first = client.get("/internal/places", headers=bff_headers).json()
    assert first["places"][0]["city"] is None

    v2 = _make_video(uid, "with_city.mp4")
    _save_results(v2, [_loc_with_address_details("Kale", 38.0001, 38.0001, {"city": "Gaziantep"})])

    second = client.get("/internal/places", headers=bff_headers).json()
    assert second["total"] == 1  # hâlâ tek Place — birleşme bozulmadı
    assert second["places"][0]["city"] == "Gaziantep"


# ─── Kategori (places_service._categorize taksonomisi) ─────────────────────

def test_category_populated_from_pipeline(client, bff_headers, registered_user):
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [_loc("Develi Restoran", 36.0, 29.0, category="Restoran")])

    data = client.get("/internal/places", headers=bff_headers).json()
    assert data["places"][0]["category"] == "Restoran"


def test_category_missing_stays_none(client, bff_headers, registered_user):
    """Eski/kategori üretemeyen bir kayıt için None'da kalmalı, hata fırlatmamalı."""
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [_loc("Kategorisiz Yer", 36.0, 29.0)])

    data = client.get("/internal/places", headers=bff_headers).json()
    assert data["places"][0]["category"] is None


def test_existing_null_category_place_gets_enriched_by_later_video(client, bff_headers, registered_user):
    """City enrichment testiyle aynı mantık: kategorisi boş bir Place, aynı
    mekanın kategorili bir sonraki tekrarıyla zenginleşebilmeli."""
    uid = registered_user["user_id"]

    v1 = _make_video(uid, "no_category.mp4")
    _save_results(v1, [_loc("Şelale", 38.0, 38.0)])

    first = client.get("/internal/places", headers=bff_headers).json()
    assert first["places"][0]["category"] is None

    v2 = _make_video(uid, "with_category.mp4")
    _save_results(v2, [_loc("Şelale", 38.0001, 38.0001, category="Şelale")])

    second = client.get("/internal/places", headers=bff_headers).json()
    assert second["total"] == 1
    assert second["places"][0]["category"] == "Şelale"


def test_library_category_filter(client, bff_headers, registered_user):
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [
        _loc("Kaputaş Plajı", 36.15, 29.45, category="Plaj"),
        _loc("Develi Restoran", 36.88, 30.70, category="Restoran"),
    ])

    resp = client.get("/internal/places?category=Plaj", headers=bff_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["places"][0]["name"] == "Kaputaş Plajı"


def test_library_category_filter_is_exact_not_substring(client, bff_headers, registered_user):
    """category taksonomisi sabit değerlerden oluşuyor — kısmi eşleşme yanlış
    sonuç döndürür (ör. 'Kale' 'Kalesi'yle karışmamalı), bu yüzden tam eşleşme."""
    vid = _make_video(registered_user["user_id"])
    _save_results(vid, [_loc("Bir Yer", 36.0, 29.0, category="Kale")])

    resp = client.get("/internal/places?category=Kal", headers=bff_headers)
    assert resp.json()["total"] == 0
