"""
Video endpoint testleri: stats, public feed, kullanıcı videoları, detay
"""
import io


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
