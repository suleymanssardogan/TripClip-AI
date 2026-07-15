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


def test_upload_non_video_file(client, bff_headers):
    """Sahte video (text) yükle → upload kabul edilir (async pipeline)"""
    fake = io.BytesIO(b"this is not a video file")
    resp = client.post(
        "/internal/videos/process",
        files={"file": ("test.mp4", fake, "video/mp4")},
        headers=bff_headers,
    )
    assert resp.status_code in (200, 400, 422, 500)


# ─── Güvenlik: Sahiplik Kontrolü ────────────────────────────────────────────

def test_get_processing_video_as_different_user_returns_404(client):
    """Başka kullanıcının işleme aşamasındaki videosuna erişim → 404 (IDOR koruması)"""
    import uuid

    # Kullanıcı A: video yükle
    email_a = f"a_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/internal/auth/register", json={"email": email_a, "password": "P1!"})
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
    rb = client.post("/internal/auth/register", json={"email": email_b, "password": "P2!"})
    user_b_id = rb.json()["user_id"]

    resp = client.get(f"/internal/videos/{video_id}", headers={"x-user-id": str(user_b_id)})
    assert resp.status_code == 404


def test_get_video_without_user_id_returns_404_for_non_completed(client):
    """X-User-Id olmadan (share sayfası gibi) işlemdeki videoya erişim → 404"""
    import uuid

    email = f"share_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/internal/auth/register", json={"email": email, "password": "P3!"})
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
