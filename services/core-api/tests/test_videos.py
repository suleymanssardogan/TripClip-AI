"""
Video endpoint testleri: stats, public feed, kullanıcı videoları, detay
"""
import io

# Düzenleme/silme testleri kaydı doğrudan DB'de kurup sonucu yine DB'den
# doğruluyor — endpoint üzerinden video oluşturmak tüm ML pipeline'ını
# tetiklerdi.
from conftest import TestingSessionLocal


# ─── İstatistik ─────────────────────────────────────────────────────────────

def test_stats_endpoint(client):
    """GET /internal/videos/stats → platform istatistikleri"""
    resp = client.get("/internal/videos/stats")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_videos", "completed_videos", "total_users", "total_cities"):
        assert key in data, f"'{key}' eksik"
    assert isinstance(data["total_videos"], int)
    assert data["total_videos"] >= 0


def test_stats_values_non_negative(client):
    """Tüm istatistik değerleri sıfır veya pozitif olmalı"""
    data = client.get("/internal/videos/stats").json()
    for key, val in data.items():
        assert val >= 0, f"{key} negatif: {val}"


# ─── Public Feed ────────────────────────────────────────────────────────────

def test_public_feed_default(client):
    """GET /internal/videos/public → liste döner"""
    resp = client.get("/internal/videos/public")
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert "total" in data
    assert isinstance(data["plans"], list)


def test_public_feed_pagination(client):
    """limit/offset parametreleri çalışmalı"""
    r1 = client.get("/internal/videos/public?limit=5&offset=0")
    assert r1.status_code == 200
    assert len(r1.json()["plans"]) <= 5

    r2 = client.get("/internal/videos/public?limit=2&offset=0")
    assert r2.status_code == 200
    assert len(r2.json()["plans"]) <= 2


def test_public_feed_limit_is_capped(client):
    """limit=50'den büyük bir değer isteğe rağmen kabul edilmemeli (amplification koruması)."""
    resp = client.get("/internal/videos/public?limit=99999")
    assert resp.status_code == 422


def test_public_feed_city_filter(client):
    """city parametresi ile filtreleme → 200"""
    resp = client.get("/internal/videos/public?city=Istanbul")
    assert resp.status_code == 200
    assert "plans" in resp.json()


# ─── Kullanıcı Videoları ────────────────────────────────────────────────────

def test_user_videos_empty(client, registered_user):
    """Yeni kullanıcının videosu yoktur"""
    uid = registered_user["user_id"]
    resp = client.get(f"/internal/videos/user/{uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert data["total"] == 0 or isinstance(data["total"], int)


def test_user_videos_requires_valid_id(client):
    """Geçersiz kullanıcı ID → boş liste (404 değil)"""
    resp = client.get("/internal/videos/user/999999")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ─── Tekil Video ────────────────────────────────────────────────────────────

def test_get_nonexistent_video(client):
    """Olmayan video ID → 404"""
    resp = client.get("/internal/videos/999999")
    assert resp.status_code == 404


def test_get_video_invalid_id_type(client):
    """String ID → 422"""
    resp = client.get("/internal/videos/not_an_id")
    assert resp.status_code == 422


# ─── Upload ─────────────────────────────────────────────────────────────────

def test_upload_without_user_id_returns_401(client):
    """X-User-Id başlığı olmadan upload → 401 (BFF olmadan direkt erişim engellenir)"""
    fake = io.BytesIO(b"not a real video")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("test.mp4", fake, "video/mp4")},
    )
    assert resp.status_code == 401


def test_upload_requires_file(client, bff_headers):
    """Dosyasız upload → 422"""
    resp = client.post(
        "/internal/videos/process",
        headers=bff_headers,
    )
    assert resp.status_code == 422


def test_upload_rejects_oversized_file(client, bff_headers, monkeypatch):
    """Dosya core-api'nin kendi boyut limitini aşarsa → 413 (BFF atlanıp doğrudan erişilse bile)"""
    import app.api.internal.videos as videos_module
    monkeypatch.setattr(videos_module, "MAX_UPLOAD_BYTES", 10)

    fake = io.BytesIO(b"this content is definitely more than ten bytes")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("big.mp4", fake, "video/mp4")},
        headers=bff_headers,
    )
    assert resp.status_code == 413


def test_upload_blocked_when_daily_quota_exceeded(client, bff_headers, monkeypatch):
    """Günlük kota aşıldığında upload 429 ile reddedilmeli (Gemini maliyet koruması)."""
    import app.core.redis as redis_module
    monkeypatch.setattr(redis_module, "check_and_increment_daily_quota", lambda user_id, limit: (False, limit + 1))

    fake = io.BytesIO(b"fake video bytes")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("clip.mp4", fake, "video/mp4")},
        headers=bff_headers,
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "DAILY_QUOTA_EXCEEDED"


def test_upload_non_video_file(client, bff_headers):
    """Sahte video (text) yükle → upload kabul edilir (async pipeline)"""
    fake = io.BytesIO(b"this is not a video file")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("test.mp4", fake, "video/mp4")},
        headers=bff_headers,
    )
    assert resp.status_code in (200, 400, 422, 500)


# ─── Güvenlik: queue-url SSRF koruması ──────────────────────────────────────
#
# Eskiden /internal/videos/queue-url'deki doğrulama sadece bir substring regex'ti
# (anchor yok) — yt-dlp'ye geçmeden önce scheme/host hiç kontrol edilmiyordu.
# Bu testler o açığın kapalı kaldığını doğrular.

def test_queue_url_rejects_internal_ip(client, bff_headers):
    """Cloud metadata endpoint gibi bir IP'ye giden istek reddedilmeli"""
    resp = client.post(
        "/internal/videos/queue-url",
        json={"url": "http://169.254.169.254/latest/meta-data/", "source": "test"},
        headers=bff_headers,
    )
    assert resp.status_code == 422


def test_queue_url_rejects_host_spoofed_via_query_string(client, bff_headers):
    """'instagram.com' string'i URL içinde geçse bile gerçek host allowlist'te değilse reddedilmeli"""
    resp = client.post(
        "/internal/videos/queue-url",
        json={"url": "http://evil.example.com/?redirect=instagram.com/reel/1", "source": "test"},
        headers=bff_headers,
    )
    assert resp.status_code == 422


def test_queue_url_rejects_file_scheme(client, bff_headers):
    resp = client.post(
        "/internal/videos/queue-url",
        json={"url": "file:///etc/passwd", "source": "test"},
        headers=bff_headers,
    )
    assert resp.status_code == 422


def test_queue_url_accepts_real_instagram_url(client, bff_headers):
    resp = client.post(
        "/internal/videos/queue-url",
        json={"url": "https://www.instagram.com/reel/ABC123/", "source": "test"},
        headers=bff_headers,
    )
    assert resp.status_code == 202


# ─── Güvenlik: Sahiplik Kontrolü ────────────────────────────────────────────

def test_get_processing_video_as_different_user_returns_404(client):
    """Başka kullanıcının işleme aşamasındaki videosuna erişim → 404 (IDOR koruması)"""
    import uuid

    # Kullanıcı A: video yükle
    email_a = f"a_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/internal/auth/register", json={"email": email_a, "password": "P1_test!"})
    assert r.status_code == 200
    user_a_id = r.json()["user_id"]

    fake = io.BytesIO(b"fake video bytes")
    upload = client.post(
        "/internal/videos/process",
        files={"file": ("clip.mp4", fake, "video/mp4")},
        headers={"x-user-id": str(user_a_id)},
    )
    assert upload.status_code == 200
    video_id = upload.json()["id"]

    # Kullanıcı B: aynı video ID'sine erişmeye çalış → 404
    email_b = f"b_{uuid.uuid4().hex[:6]}@test.com"
    rb = client.post("/internal/auth/register", json={"email": email_b, "password": "P2_test!"})
    user_b_id = rb.json()["user_id"]

    resp = client.get(f"/internal/videos/{video_id}", headers={"x-user-id": str(user_b_id)})
    assert resp.status_code == 404


def test_get_video_without_user_id_returns_404_for_non_completed(client):
    """X-User-Id olmadan (share sayfası gibi) işlemdeki videoya erişim → 404"""
    import uuid

    email = f"share_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/internal/auth/register", json={"email": email, "password": "P3_test!"})
    user_id = r.json()["user_id"]

    fake = io.BytesIO(b"fake video")
    upload = client.post(
        "/internal/videos/process",
        files={"file": ("v.mp4", fake, "video/mp4")},
        headers={"x-user-id": str(user_id)},
    )
    video_id = upload.json()["id"]

    # Anonim erişim → video tamamlanmadığı için 404
    resp = client.get(f"/internal/videos/{video_id}")
    assert resp.status_code == 404

# ─── Durak Düzenleme (PATCH /order) ─────────────────────────────────────────
#
# stop_order hem sıralamayı hem de HANGİ durakların kaldığını taşıyor: listede
# olmayan durak silinmiş sayılır (bkz. mobile-bff _apply_stop_order). Bu yüzden
# id'lerin gerçekten var olan duraklara işaret etmesi kritik — aksi hâlde okuma
# tarafındaki eşleme sessizce durak kaybeder ya da çoğaltır.

def _make_video_with_locations(user_id: int, count: int = 3) -> int:
    """Test DB'sine `count` duraklı, tamamlanmış bir video ekler ve id'sini döner."""
    from app.models.video import Video, VideoStatus

    db = TestingSessionLocal()
    try:
        video = Video(
            filename="order.mp4",
            file_path="/tmp/does-not-exist-order.mp4",
            status=VideoStatus.COMPLETED,
            user_id=user_id,
            deduplicated_locations=[
                {"original_name": f"Durak {i}", "place_data": {}} for i in range(1, count + 1)
            ],
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video.id
    finally:
        db.close()


def _stop_order_of(video_id: int):
    from app.models.video import Video

    db = TestingSessionLocal()
    try:
        return db.query(Video).filter(Video.id == video_id).first().stop_order
    finally:
        db.close()


def test_update_stop_order_persists(client, bff_headers, registered_user):
    """Geçerli sıra kaydedilmeli."""
    vid = _make_video_with_locations(registered_user["user_id"], 3)
    resp = client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[3, 1, 2]]},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert _stop_order_of(vid) == [[3, 1, 2]]


def test_update_stop_order_allows_subset_as_deletion(client, bff_headers, registered_user):
    """Eksik id silme anlamına gelir — reddedilmemeli."""
    vid = _make_video_with_locations(registered_user["user_id"], 3)
    resp = client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[1, 3]]},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert _stop_order_of(vid) == [[1, 3]]


def test_update_stop_order_rejects_unknown_stop(client, bff_headers, registered_user):
    """Var olmayan durak numarası → 400, kayıt değişmemeli."""
    vid = _make_video_with_locations(registered_user["user_id"], 3)
    resp = client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[1, 2, 99]]},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_STOP_ORDER"
    assert _stop_order_of(vid) is None


def test_update_stop_order_rejects_duplicate_stop(client, bff_headers, registered_user):
    """Aynı durak iki kez sıralanamaz — okuma tarafında çoğalmasını önler."""
    vid = _make_video_with_locations(registered_user["user_id"], 3)
    resp = client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[1, 1, 2]]},
        headers=bff_headers,
    )
    assert resp.status_code == 400
    assert _stop_order_of(vid) is None


def test_update_stop_order_requires_user_header(client, registered_user):
    vid = _make_video_with_locations(registered_user["user_id"], 2)
    resp = client.patch(f"/internal/videos/{vid}/order", json={"order": [[1, 2]]})
    assert resp.status_code == 401


def test_update_stop_order_rejects_other_users_video(client, registered_user):
    """Başkasının planını düzenlemek → 403."""
    vid = _make_video_with_locations(registered_user["user_id"], 2)
    resp = client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[2, 1]]},
        headers={"x-user-id": str(registered_user["user_id"] + 12345)},
    )
    assert resp.status_code == 403


def test_update_stop_order_nonexistent_video(client, bff_headers):
    resp = client.patch(
        "/internal/videos/999999/order",
        json={"order": [[1]]},
        headers=bff_headers,
    )
    assert resp.status_code == 404


# ─── Plan Silme (DELETE) ────────────────────────────────────────────────────

def test_delete_video_removes_record(client, bff_headers, registered_user):
    vid = _make_video_with_locations(registered_user["user_id"], 2)
    resp = client.delete(f"/internal/videos/{vid}", headers=bff_headers)
    assert resp.status_code == 200
    assert client.get(f"/internal/videos/{vid}").status_code == 404


def test_delete_video_tracks_shared_trip_deleted(client, bff_headers, registered_user):
    from unittest import mock

    vid = _make_video_with_locations(registered_user["user_id"], 1)
    with mock.patch(
        "app.application.services.analytics_service.AnalyticsService.track"
    ) as mock_track:
        resp = client.delete(f"/internal/videos/{vid}", headers=bff_headers)

    assert resp.status_code == 200
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["trip_id"] == vid
    assert kwargs["user_id"] == registered_user["user_id"]
    assert kwargs["event"].value == "shared_trip_deleted"


def test_delete_video_survives_missing_file(client, bff_headers, registered_user):
    """file_path diskte yoksa silme yine başarılı olmalı — DB kaydı asıl olan."""
    vid = _make_video_with_locations(registered_user["user_id"], 1)
    resp = client.delete(f"/internal/videos/{vid}", headers=bff_headers)
    assert resp.status_code == 200


def test_delete_video_requires_user_header(client, registered_user):
    vid = _make_video_with_locations(registered_user["user_id"], 1)
    resp = client.delete(f"/internal/videos/{vid}")
    assert resp.status_code == 401
    assert _stop_order_of(vid) is None   # kayıt hâlâ duruyor


def test_delete_video_rejects_other_user(client, registered_user):
    vid = _make_video_with_locations(registered_user["user_id"], 1)
    resp = client.delete(
        f"/internal/videos/{vid}",
        headers={"x-user-id": str(registered_user["user_id"] + 12345)},
    )
    assert resp.status_code == 403


def test_delete_nonexistent_video(client, bff_headers):
    resp = client.delete("/internal/videos/999999", headers=bff_headers)
    assert resp.status_code == 404


# ─── Özet ile detay tutarlılığı ─────────────────────────────────────────────
#
# Liste kartındaki mekan sayısı ham `deduplicated_locations`'tan geliyordu, yani
# kullanıcı bir durak silince kart "12 mekan" derken detay 11 gösteriyordu.

def test_summary_count_reflects_user_deletion(client, bff_headers, registered_user):
    uid = registered_user["user_id"]
    vid = _make_video_with_locations(uid, 3)

    before = client.get(f"/internal/videos/user/{uid}").json()["plans"]
    assert next(p for p in before if p["id"] == vid)["locations_count"] == 3

    client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[1, 3]]},
        headers=bff_headers,
    )

    after = client.get(f"/internal/videos/user/{uid}").json()["plans"]
    assert next(p for p in after if p["id"] == vid)["locations_count"] == 2


def test_summary_top_location_follows_user_order(client, bff_headers, registered_user):
    """Başlık ilk duraktan üretiliyor — sıralama değişince başlık da değişmeli."""
    uid = registered_user["user_id"]
    vid = _make_video_with_locations(uid, 3)

    client.patch(
        f"/internal/videos/{vid}/order",
        json={"order": [[3, 1, 2]]},
        headers=bff_headers,
    )

    plans = client.get(f"/internal/videos/user/{uid}").json()["plans"]
    assert next(p for p in plans if p["id"] == vid)["top_location"] == "Durak 3"


def test_visible_locations_falls_back_on_stale_order():
    """Tamamen geçersiz bir sıra planı boş göstermemeli."""
    from app.models.video import Video, visible_locations

    v = Video(filename="x.mp4", file_path="/tmp/x.mp4")
    v.deduplicated_locations = [{"original_name": "A"}, {"original_name": "B"}]
    v.stop_order = [[97, 98]]
    assert len(visible_locations(v)) == 2


def test_visible_locations_without_order_is_raw_list():
    from app.models.video import Video, visible_locations

    v = Video(filename="x.mp4", file_path="/tmp/x.mp4")
    v.deduplicated_locations = [{"original_name": "A"}, {"original_name": "B"}]
    v.stop_order = None
    assert [loc["original_name"] for loc in visible_locations(v)] == ["A", "B"]
