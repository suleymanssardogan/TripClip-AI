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


# ─── Durak Düzenleme / Silme ────────────────────────────────────────────────

def test_update_stop_order_missing_jwt(client):
    resp = client.patch("/api/mobile/videos/1/order", json={"order": [[1, 2]]})
    assert resp.status_code == 403


def test_update_stop_order_forwards_user_id(client, auth_headers, mock_core_api, make_response):
    """Sıra core-api'ye iletilir, user_id JWT'den türetilir (istemciden değil)."""
    mock_core_api.patch.return_value = make_response(200, {"success": True})

    resp = client.patch(
        "/api/mobile/videos/7/order",
        json={"order": [[3, 1]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    args, kwargs = mock_core_api.patch.call_args
    assert args[0].endswith("/internal/videos/7/order")
    assert kwargs["json"] == {"order": [[3, 1]]}
    assert kwargs["headers"]["x-user-id"] == "1"


def test_update_stop_order_propagates_core_error(client, auth_headers, mock_core_api, make_response):
    """core-api geçersiz sırayı reddederse istemci de hata görmeli."""
    mock_core_api.patch.return_value = make_response(
        400, {"error": {"code": "INVALID_STOP_ORDER", "message": "Geçersiz durak numarası: [99]."}}
    )
    resp = client.patch(
        "/api/mobile/videos/7/order",
        json={"order": [[99]]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_delete_video_missing_jwt(client):
    resp = client.delete("/api/mobile/videos/1")
    assert resp.status_code == 403


def test_delete_video_forwards_user_id(client, auth_headers, mock_core_api, make_response):
    mock_core_api.delete.return_value = make_response(200, {"success": True})

    resp = client.delete("/api/mobile/videos/7", headers=auth_headers)
    assert resp.status_code == 200

    args, kwargs = mock_core_api.delete.call_args
    assert args[0].endswith("/internal/videos/7")
    assert kwargs["headers"]["x-user-id"] == "1"


def test_delete_video_propagates_forbidden(client, auth_headers, mock_core_api, make_response):
    """Başkasının planı → core-api PERMISSION_DENIED, BFF de 403 döndürmeli."""
    mock_core_api.delete.return_value = make_response(
        403, {"error": {"code": "PERMISSION_DENIED", "message": "Bu videoyu silme yetkiniz yok."}}
    )
    resp = client.delete("/api/mobile/videos/7", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "PERMISSION_DENIED"


# ─── Transformer: stop_order uygulaması ─────────────────────────────────────
#
# stop_order hem sıralamayı hem hangi durakların kaldığını taşıyor — bu yüzden
# eksik id "silinmiş", bilinmeyen id ise "eskimiş sıra" anlamına geliyor.

def _raw_detail(stop_order=None, count=3):
    locs = [
        {
            "original_name": f"Durak {i}",
            "place_data": {"type": "place", "location": {"lat": 36.0 + i, "lng": 30.0 + i}},
        }
        for i in range(1, count + 1)
    ]
    return {
        "id": 1, "filename": "a.mp4", "status": "completed", "duration": 10,
        "created_at": "2026-07-30T10:00:00",
        "ai_results": {"nominatim": {"deduplicated_locations": locs}},
        "stop_order": stop_order,
    }


def test_transformer_without_stop_order_keeps_ai_order():
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail())
    assert [loc["index"] for loc in out["locations"]] == [1, 2, 3]


def test_transformer_applies_user_order():
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[3, 1, 2]]))
    assert [loc["index"] for loc in out["locations"]] == [3, 1, 2]
    # Rota çizgisi de kullanıcının sırasını izlemeli
    assert [p["name"] for p in out["route"]] == ["Durak 3", "Durak 1", "Durak 2"]


def test_transformer_treats_missing_id_as_deleted():
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[1, 3]]))
    assert [loc["index"] for loc in out["locations"]] == [1, 3]
    assert len(out["locations"]) == 2


def test_transformer_keeps_index_stable_not_renumbered():
    """index kalıcı kimlik — istemci sonraki düzenlemede aynı id'yi geri gönderiyor."""
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[2, 3]]))
    assert [loc["index"] for loc in out["locations"]] == [2, 3]


def test_transformer_ignores_unknown_ids_in_order():
    """Eskimiş sıradaki bilinmeyen id atlanır, bilinen duraklar korunur."""
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[99, 2]]))
    assert [loc["index"] for loc in out["locations"]] == [2]


def test_transformer_falls_back_when_order_matches_nothing():
    """Tamamen eskimiş sıra yüzünden kullanıcıya boş plan gösterilmemeli."""
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[98, 99]]))
    assert [loc["index"] for loc in out["locations"]] == [1, 2, 3]


def test_transformer_flattens_multi_day_order_from_web():
    """Web çok günlü kaydedebiliyor; mobil tek liste görmeli."""
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[2], [1, 3]]))
    assert [loc["index"] for loc in out["locations"]] == [2, 1, 3]


def test_transformer_single_stop_has_no_route():
    from app.transformers.video_transformer import to_mobile_detail

    out = to_mobile_detail(_raw_detail(stop_order=[[2]]))
    assert out["route"] is None
