"""
Web BFF — Video endpoint testleri: auth guard, upload, protected/public route'lar.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""
import io


# ─── Auth guard — JWT eksik / geçersiz ───────────────────────────────────────
# Web BFF, mobile-bff'in aksine HTTPBearer(auto_error=False) kullanır — bu yüzden
# header hiç yoksa da bozuksa da get_current_user_id kendi 401'ini fırlatır (403 değil).

def test_upload_missing_jwt(client):
    files = {"file": ("trip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
    resp = client.post("/api/web/videos/upload", files=files)
    assert resp.status_code == 401


def test_upload_invalid_jwt(client):
    files = {"file": ("trip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
    resp = client.post(
        "/api/web/videos/upload",
        files=files,
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


def test_queue_url_missing_jwt(client):
    resp = client.post("/api/web/videos/queue-url", json={"url": "https://instagram.com/reel/abc"})
    assert resp.status_code == 401


def test_queue_url_invalid_jwt(client):
    resp = client.post(
        "/api/web/videos/queue-url",
        json={"url": "https://instagram.com/reel/abc"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


# ─── Upload ─────────────────────────────────────────────────────────────────

def test_upload_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"id": 99, "status": "queued"})

    files = {"file": ("trip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
    resp = client.post("/api/web/videos/upload", files=files, headers=auth_headers)

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
    resp = client.post("/api/web/videos/upload", files=files, headers=auth_headers)

    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_FILE_TYPE"
    mock_core_api.post.assert_not_awaited()


def test_upload_file_too_large(client, auth_headers, mock_core_api):
    """200MB üstü dosya → 400 FILE_TOO_LARGE, Core API'ye hiç gidilmez."""
    big_content = b"0" * (200 * 1024 * 1024 + 1)
    files = {"file": ("trip.mp4", io.BytesIO(big_content), "video/mp4")}
    resp = client.post("/api/web/videos/upload", files=files, headers=auth_headers)

    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TOO_LARGE"
    mock_core_api.post.assert_not_awaited()


# ─── Public routes (JWT opsiyonel) ───────────────────────────────────────────

def test_get_video_public_no_jwt(client, mock_core_api, make_response):
    """Video detayı JWT olmadan da görüntülenebilir (share/[id] sayfası için)."""
    mock_core_api.get.return_value = make_response(200, {
        "id": 5, "filename": "trip.mp4", "status": "completed",
    })

    resp = client.get("/api/web/videos/5")

    assert resp.status_code == 200
    assert resp.json()["id"] == 5


def test_get_video_not_found_passthrough(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(404, {
        "error": {"code": "VIDEO_NOT_FOUND", "message": "not found"},
    })

    resp = client.get("/api/web/videos/999")

    assert resp.status_code == 404
    assert resp.json()["code"] == "VIDEO_NOT_FOUND"


def test_get_video_progress_no_jwt(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"stage": "ner", "percent": 40})

    resp = client.get("/api/web/videos/5/progress")

    assert resp.status_code == 200
    assert resp.json()["percent"] == 40


def test_get_video_progress_core_api_error_falls_back(client, mock_core_api, make_response):
    """Progress alınamazsa UI'ı bloklamamak için varsayılan değer dönülmeli, hata değil."""
    mock_core_api.get.return_value = make_response(500, {"error": {"code": "INTERNAL_SERVER_ERROR"}})

    resp = client.get("/api/web/videos/5/progress")

    assert resp.status_code == 200
    assert resp.json() == {"stage": "processing", "percent": 10}


# ─── queue-url ────────────────────────────────────────────────────────────────

def test_queue_url_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(202, {"id": 12, "status": "queued"})

    resp = client.post(
        "/api/web/videos/queue-url",
        json={"url": "https://instagram.com/reel/abc123"},
        headers=auth_headers,
    )

    assert resp.status_code == 202
    assert resp.json()["id"] == 12


def test_queue_url_invalid_payload(client, auth_headers, mock_core_api):
    """url alanı eksikse Core API'ye hiç gidilmeden 422 dönmeli."""
    resp = client.post("/api/web/videos/queue-url", json={}, headers=auth_headers)
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()
