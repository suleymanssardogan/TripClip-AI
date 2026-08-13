"""
Mobile BFF — Trip Assistant proxy testleri. Core API gerçekten çağrılmaz —
trip_optimization testleriyle AYNI desen (mock_core_api/make_response).
"""

# ─── Authentication ───────────────────────────────────────────────────────────

def test_assistant_requires_auth(client):
    resp = client.post("/api/mobile/trips/1/assistant", json={"message": "soru"})
    assert resp.status_code == 403  # HTTPBearer(auto_error=True) — bkz. trip_optimization testlerinin aynı notu


# ─── Unit: route/forwarding davranışı ──────────────────────────────────────────

def test_assistant_happy_path(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "answer": "Bugün ilk durağın Antep.",
        "references": [{"type": "stop", "day_index": 0, "place_id": 25}],
    })

    resp = client.post(
        "/api/mobile/trips/2/assistant",
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
        "/api/mobile/trips/2/assistant",
        json={
            "message": "peki ya yarın?",
            "history": [{"role": "user", "content": "Bugün nereye gideceğim?"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    _, kwargs = mock_core_api.post.call_args
    assert kwargs["json"]["history"] == [{"role": "user", "content": "Bugün nereye gideceğim?"}]


# ─── Hata yayılımı ──────────────────────────────────────────────────────────

def test_assistant_propagates_empty_message_as_400(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        400, {"error": {"code": "INVALID_ASSISTANT_REQUEST", "message": "Boş bir mesaj gönderilemez."}}
    )
    resp = client.post("/api/mobile/trips/2/assistant", json={"message": ""}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_ASSISTANT_REQUEST"


def test_assistant_propagates_trip_not_found_as_404(client, auth_headers, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(
        404, {"error": {"code": "TRIP_NOT_FOUND", "message": "not found"}}
    )
    resp = client.post("/api/mobile/trips/999/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "TRIP_NOT_FOUND"


def test_assistant_propagates_unavailable_as_500(client, auth_headers, mock_core_api, make_response):
    # Mobile-bff'nin kendi mevcut kuralı: ML_SERVICE_UNAVAILABLE/DATABASE_ERROR
    # gibi "sağlayıcı/servis hazır değil" sınıfı 503 DEĞİL 500'e eşlenir
    # (web-bff'nin aksine) — bkz. error_wrapper.py'nin AYNI önceden var olan
    # asimetrisi, burada yalnızca ASSISTANT_UNAVAILABLE için de UYGULANDI.
    mock_core_api.post.return_value = make_response(
        503, {"error": {"code": "ASSISTANT_UNAVAILABLE", "message": "AI asistanı şu anda kullanılamıyor."}}
    )
    resp = client.post("/api/mobile/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 500
    assert resp.json()["code"] == "ASSISTANT_UNAVAILABLE"


def test_assistant_core_api_unreachable_returns_503(client, auth_headers, mock_core_api):
    import httpx
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")
    resp = client.post("/api/mobile/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 503


def test_assistant_rate_limit(client, auth_headers, mock_core_api, make_response):
    """M33 — assistant route 20/dakika limiti (videos.py'nin AYNI test deseni) —
    21. istekte 429 dönmeli. Her LLM çağrısının gerçek maliyeti/gecikmesi
    olduğu için bu route artık ÖNCEDEN olmayan bir per-route limit taşıyor."""
    mock_core_api.post.return_value = make_response(200, {"answer": "Cevap", "references": []})

    for i in range(20):
        r = client.post("/api/mobile/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
        assert r.status_code == 200, f"{i+1}. istek beklenmedik şekilde başarısız: {r.status_code}"

    resp = client.post("/api/mobile/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 429


def test_assistant_core_api_timeout_returns_504_not_a_hang(client, auth_headers, mock_core_api):
    # M33 — core-api tarafı (Gemini/Ollama + M32'nin araç döngüsü) beklenenden
    # uzun sürerse (bkz. internal_client(60.0)), BFF sonsuza kadar ASILI
    # KALMAZ — httpx'in kendi zaman aşımı devreye girer ve temiz bir
    # 504 GATEWAY_TIMEOUT döner, ham bir bağlantı hatası/istisna SIZMAZ.
    import httpx
    mock_core_api.post.side_effect = httpx.ReadTimeout("timed out")
    resp = client.post("/api/mobile/trips/2/assistant", json={"message": "soru"}, headers=auth_headers)
    assert resp.status_code == 504
    assert resp.json()["code"] == "GATEWAY_TIMEOUT"
