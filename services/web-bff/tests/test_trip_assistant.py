"""
Web BFF — Trip Assistant proxy testleri. Core API gerçekten çağrılmaz —
trip_optimization testleriyle AYNI desen (mock_core_api/make_response).
"""

# ─── Authentication ───────────────────────────────────────────────────────────

def test_assistant_requires_auth(client):
    resp = client.post("/api/web/trips/1/assistant", json={"message": "soru"})
    assert resp.status_code == 401


# ─── Unit: route/forwarding davranışı ──────────────────────────────────────────

def test_assistant_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "answer": "Bugün ilk durağın Antep.",
        "references": [{"type": "stop", "day_index": 0, "place_id": 25}],
    })

    resp = client.post(
        "/api/web/trips/2/assistant",
        json={"message": "Bugün nereye gideceğim?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Bugün ilk durağın Antep."
    assert data["references"] == [{"type": "stop", "day_index": 0, "place_id": 25}]

    args, kwargs = mock_core_api.post.call_args
    assert args[0].endswith("/internal/trips/2/assistant")
    assert kwargs["headers"]["x-user-id"] == "1"
    assert kwargs["json"]["message"] == "Bugün nereye gideceğim?"


def test_assistant_forwards_bounded_history(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"answer": "Cevap", "references": []})

    resp = client.post(
        "/api/web/trips/2/assistant",
        json={
            "message": "peki ya yarın?",
            "history": [
                {"role": "user", "content": "Bugün nereye gideceğim?"},
                {"role": "assistant", "content": "İlk durağın Antep."},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    _, kwargs = mock_core_api.post.call_args
    assert kwargs["json"]["history"] == [
        {"role": "user", "content": "Bugün nereye gideceğim?"},
        {"role": "assistant", "content": "İlk durağın Antep."},
    ]


# ─── Hata yayılımı ──────────────────────────────────────────────────────────

def test_assistant_propagates_empty_message_as_400(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_ASSISTANT_REQUEST", "message": "Boş bir mesaj gönderilemez."}}
    )
    resp = client.post("/api/web/trips/2/assistant", json={"message": ""}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_ASSISTANT_REQUEST"


def test_assistant_propagates_trip_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "not found"}}
    )
    resp = client.post("/api/web/trips/999/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "TRIP_NOT_FOUND"


def test_assistant_propagates_unavailable_as_503(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        503, {"error": {"code": "ASSISTANT_UNAVAILABLE", "message": "AI asistanı şu anda kullanılamıyor."}}
    )
    resp = client.post("/api/web/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["code"] == "ASSISTANT_UNAVAILABLE"


def test_assistant_propagates_upstream_internal_error(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        500, {"error": {"code": "INTERNAL_SERVER_ERROR", "message": "boom"}}
    )
    resp = client.post("/api/web/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 503


def test_assistant_core_api_unreachable_returns_503(client, auth_headers, mock_core_api):
    import httpx
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")
    resp = client.post("/api/web/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 503
