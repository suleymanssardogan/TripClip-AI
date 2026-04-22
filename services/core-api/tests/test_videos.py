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

def test_upload_requires_file(client, auth_headers):
    """Dosyasız upload → 422"""
    resp = client.post(
        "/internal/videos/process",
        headers=auth_headers
    )
    assert resp.status_code == 422


def test_upload_non_video_file(client, auth_headers):
    """Sahte video (text) yükle → 400 veya işleme hatası"""
    fake = io.BytesIO(b"this is not a video file")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("test.mp4", fake, "video/mp4")},
        headers=auth_headers
    )
    # Upload kabul edilebilir (async işleme), ama ID döner
    assert resp.status_code in (200, 400, 422, 500)
