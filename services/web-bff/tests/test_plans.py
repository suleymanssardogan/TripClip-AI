"""
Web BFF — Plans route testleri: public feed, stats, user plans, analyze/editor/share
transform'ları, ve editor durak sırası kaydetme (PATCH /order).

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır.
"""
from unittest import mock


# ─── GET /plans — public feed ────────────────────────────────────────────────

def test_get_plans_happy_path(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "plans": [{
            "id": 1, "filename": "trip.mp4", "status": "completed",
            "duration": 30, "created_at": "2026-01-01T00:00:00",
            "locations_count": 3, "top_location": "Antalya",
            "ocr_preview": ["Kaputaş"], "processing_time": 12.5,
        }],
        "total": 1,
    })

    resp = client.get("/api/web/plans")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["plans"][0]["topLocation"] == "Antalya"  # to_web_card camelCase dönüşümü


def test_get_plans_returns_empty_list_on_404(client, mock_core_api, make_response):
    """Core API 404 dönerse (henüz hiç plan yoksa) boş liste dönmeli, hata değil."""
    mock_core_api.get.return_value = make_response(404, {})
    resp = client.get("/api/web/plans")
    assert resp.status_code == 200
    assert resp.json() == {"plans": [], "total": 0}


# ─── GET /plans/stats ─────────────────────────────────────────────────────────

def test_get_stats_happy_path(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "total_videos": 10, "completed_videos": 8, "total_users": 4, "total_cities": 3,
    })
    resp = client.get("/api/web/plans/stats")
    assert resp.status_code == 200
    assert resp.json()["total_videos"] == 10


def test_get_stats_falls_back_to_zeros_on_error(client, mock_core_api, make_response):
    """İstatistik alınamazsa dashboard'u bloklamamak için sıfır dönmeli, hata değil."""
    mock_core_api.get.return_value = make_response(500, {"error": {"code": "INTERNAL_SERVER_ERROR"}})
    resp = client.get("/api/web/plans/stats")
    assert resp.status_code == 200
    assert resp.json() == {"total_videos": 0, "total_cities": 0, "total_users": 0, "completed_videos": 0}


# ─── GET /plans/user/{user_id} ────────────────────────────────────────────────

def test_get_user_plans_happy_path(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "plans": [{
            "id": 2, "filename": "a.mp4", "status": "completed", "duration": 10,
            "created_at": None, "locations_count": 0, "top_location": None,
            "ocr_preview": [], "processing_time": None,
        }],
        "total": 1,
    })
    resp = client.get("/api/web/plans/user/1")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_user_plans_surfaces_real_errors(client, mock_core_api, make_response):
    """core-api'nin /user/{id} route'u için >=400 her zaman gerçek bir arızadır
    (kullanıcının hiç videosu olmaması ayrı bir 200+boş liste yoluyla döner) —
    dashboard'ın "hata" ile "henüz video yok" durumunu ayırt edebilmesi için
    bu artık sessizce boş listeye düşürülmeden frontend'e yansıtılmalı."""
    mock_core_api.get.return_value = make_response(500, {"error": {"code": "DATABASE_ERROR"}})
    resp = client.get("/api/web/plans/user/1")
    assert resp.status_code == 503
    assert resp.json()["code"] == "DATABASE_ERROR"


# ─── GET /plans/{id} ve transform view'ları ──────────────────────────────────

def test_get_plan_raw_passthrough(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "id": 7, "filename": "x.mp4", "status": "completed", "duration": 5,
        "created_at": "2026-01-01T00:00:00", "ai_results": None,
        "degradation": None, "stop_order": None,
    })
    resp = client.get("/api/web/plans/7")
    assert resp.status_code == 200
    assert resp.json()["id"] == 7


def test_get_plan_not_found_passthrough(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(404, {
        "error": {"code": "VIDEO_NOT_FOUND", "message": "not found"},
    })
    resp = client.get("/api/web/plans/999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "VIDEO_NOT_FOUND"


def test_get_plan_analyze_transforms_locations(client, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {
        "id": 3, "filename": "trip.mp4", "status": "completed", "duration": 20,
        "ai_results": {
            "processing_time": 5.0,
            "detections": {"count": 2},
            "nominatim": {"deduplicated_locations": [
                {"original_name": "Kaputaş", "place_data": {
                    "name": "Kaputaş Plajı", "type": "beach",
                    "location": {"lat": 36.16, "lng": 29.63}, "importance": 0.8,
                }},
            ]},
            "rag": {"travel_tips": {"tips": [], "summary": ""}},
            "route": {"optimized_route": {}},
            "audio": {"transcription": {}},
            "ocr_pois": [],
        },
    })
    resp = client.get("/api/web/plans/3/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["locationsCount"] == 1
    assert data["locations"][0]["name"] == "Kaputaş"


# ─── PATCH /plans/{id}/order — editor durak sırası kaydetme ──────────────────

def test_update_plan_order_requires_jwt(client):
    resp = client.patch("/api/web/plans/1/order", json={"order": [[1, 2]]})
    assert resp.status_code == 401


def test_update_plan_order_happy_path(client, auth_headers, make_response):
    with mock.patch("httpx.AsyncClient.patch", new_callable=mock.AsyncMock) as mock_patch:
        mock_patch.return_value = make_response(200, {"success": True})
        resp = client.patch(
            "/api/web/plans/1/order",
            json={"order": [[3, 1, 2]]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    # user_id JWT'den türetilip x-user-id header'ı olarak core-api'ye iletilmeli
    _, kwargs = mock_patch.call_args
    assert kwargs["headers"]["x-user-id"] == "1"
    assert kwargs["json"] == {"order": [[3, 1, 2]]}


def test_update_plan_order_permission_denied_passthrough(client, auth_headers, make_response):
    """Başka kullanıcının videosunu düzenlemeye çalışmak → core-api'nin 403'ü BFF'e yansımalı."""
    with mock.patch("httpx.AsyncClient.patch", new_callable=mock.AsyncMock) as mock_patch:
        mock_patch.return_value = make_response(403, {
            "error": {"code": "PERMISSION_DENIED", "message": "Bu videoyu düzenleme yetkiniz yok."},
        })
        resp = client.patch(
            "/api/web/plans/1/order",
            json={"order": [[1]]},
            headers=auth_headers,
        )

    assert resp.status_code == 403
    assert resp.json()["code"] == "PERMISSION_DENIED"


def test_update_plan_order_invalid_payload(client, auth_headers):
    """order alanı eksikse core-api'ye hiç gidilmeden 422 dönmeli."""
    with mock.patch("httpx.AsyncClient.patch", new_callable=mock.AsyncMock) as mock_patch:
        resp = client.patch("/api/web/plans/1/order", json={}, headers=auth_headers)
    assert resp.status_code == 422
    mock_patch.assert_not_awaited()
