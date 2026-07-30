"""
Mobile BFF — Video endpoint testleri: auth guard, upload, protected route'lar.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""
import io


# ─── Auth guard — JWT eksik / geçersiz ───────────────────────────────────────

def test_get_user_videos_missing_jwt(client):
    """Authorization header hiç yoksa HTTPBearer 403 döner (FastAPI varsayılanı)."""
    resp = client.get("/api/mobile/videos")
    assert resp.status_code == 403


def test_get_user_videos_invalid_jwt(client):
    """Bozuk/imzasız token → get_current_user_id 401 fırlatır."""
    resp = client.get("/api/mobile/videos", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_video_detail_missing_jwt(client):
    resp = client.get("/api/mobile/videos/1")
    assert resp.status_code == 403


def test_upload_missing_jwt(client):
    files = {"file": ("trip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
    resp = client.post("/api/mobile/videos/upload", files=files)
    assert resp.status_code == 403


# ─── Upload ─────────────────────────────────────────────────────────────────

def test_upload_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"id": 99, "status": "queued"})

    files = {"file": ("trip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
    resp = client.post("/api/mobile/videos/upload", files=files, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 99
    assert data["status"] == "queued"
    # x-user-id header'ı core-api'ye iletilmeli — spoofing yerine JWT'den türetilmiş user_id
    _, kwargs = mock_core_api.post.call_args
    assert kwargs["headers"]["x-user-id"] == "1"


def test_upload_invalid_file_type(client, auth_headers, mock_core_api):
    """Video olmayan bir dosya → 400, Core API'ye hiç gidilmez."""
    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    resp = client.post("/api/mobile/videos/upload", files=files, headers=auth_headers)

    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_FILE_TYPE"
    mock_core_api.post.assert_not_awaited()


def test_upload_file_too_large(client, auth_headers, mock_core_api):
    """100MB üstü dosya → 400 FILE_TOO_LARGE, Core API'ye hiç gidilmez."""
    big_content = b"0" * (100 * 1024 * 1024 + 1)
    files = {"file": ("trip.mp4", io.BytesIO(big_content), "video/mp4")}
    resp = client.post("/api/mobile/videos/upload", files=files, headers=auth_headers)

    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TOO_LARGE"
    mock_core_api.post.assert_not_awaited()


def test_upload_rate_limit(client, auth_headers, mock_core_api, make_response):
    """Upload endpoint 10/dakika limiti — 11. istekte 429 dönmeli."""
    mock_core_api.post.return_value = make_response(200, {"id": 1, "status": "queued"})

    for i in range(10):
        files = {"file": ("trip.mp4", io.BytesIO(b"x"), "video/mp4")}
        r = client.post("/api/mobile/videos/upload", files=files, headers=auth_headers)
        assert r.status_code == 200, f"{i+1}. istek beklenmedik şekilde başarısız: {r.status_code}"

    files = {"file": ("trip.mp4", io.BytesIO(b"x"), "video/mp4")}
    resp = client.post("/api/mobile/videos/upload", files=files, headers=auth_headers)
    assert resp.status_code == 429


# ─── Protected route happy path ──────────────────────────────────────────────

def test_get_user_videos_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "plans": [{"id": 1, "filename": "trip.mp4", "status": "completed", "locations_count": 3}],
        "total": 1,
    })

    resp = client.get("/api/mobile/videos", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["plans"][0]["id"] == 1
    # to_mobile_summary() camelCase alanlara dönüştürmeli
    assert "locationsCount" in data["plans"][0]


def test_video_detail_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "id": 5,
        "filename": "trip.mp4",
        "status": "completed",
        "duration": 30,
        "created_at": "2026-01-01T00:00:00",
        "ai_results": {},
    })

    resp = client.get("/api/mobile/videos/5", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["id"] == 5


def test_video_detail_not_found_passthrough(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(404, {
        "error": {"code": "VIDEO_NOT_FOUND", "message": "not found"},
    })

    resp = client.get("/api/mobile/videos/999", headers=auth_headers)

    assert resp.status_code == 404
    assert resp.json()["code"] == "VIDEO_NOT_FOUND"


def test_queue_url_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(202, {"id": 12, "status": "queued"})

    resp = client.post(
        "/api/mobile/videos/queue-url",
        json={"url": "https://instagram.com/reel/abc123"},
        headers=auth_headers,
    )

    assert resp.status_code == 202
    assert resp.json()["id"] == 12


def test_queue_url_invalid_payload(client, auth_headers, mock_core_api):
    """url alanı eksikse Core API'ye hiç gidilmeden 422 dönmeli."""
    resp = client.post("/api/mobile/videos/queue-url", json={}, headers=auth_headers)
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_queue_url_missing_jwt(client):
    resp = client.post("/api/mobile/videos/queue-url", json={"url": "https://instagram.com/reel/abc"})
    assert resp.status_code == 403
