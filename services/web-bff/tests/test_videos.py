"""
Web BFF — Video endpoint testleri: protected/public route'lar.
Video capture iOS-only — upload/queue-url endpoint'i yok, bu dosya yalnızca
görüntüleme (progress, detay) route'larını test eder.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


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
