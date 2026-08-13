"""
Sağlık kontrol testleri
"""
from unittest import mock


def test_health_check(client):
    """GET /health → 200 + healthy"""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "core-api"


def test_root_redirect(client):
    """GET / → 200 veya redirect"""
    resp = client.get("/", follow_redirects=True)
    assert resp.status_code in (200, 404)  # docs veya 404 kabul


# ─── /health/ready — ai_provider bloğu (M29) ────────────────────────────────
# Bu testler yalnızca YENİ `ai_provider` bloğunu doğrular, mevcut
# `checks`/`all_ok` altyapı (postgres/redis) gate'ini DEĞİL.

def test_health_ready_reports_gemini_configured(client, monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    resp = client.get("/health/ready")
    ai_provider = resp.json()["ai_provider"]
    assert ai_provider["provider"] == "gemini"
    assert ai_provider["status"] == "configured"
    assert ai_provider["detail"] is None
    assert "test-key-not-real" not in resp.text


def test_health_ready_reports_gemini_not_configured_without_crashing(client, monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resp = client.get("/health/ready")
    assert resp.json()["ai_provider"]["provider"] == "gemini"
    assert resp.json()["ai_provider"]["status"] == "not_configured"


def test_health_ready_ollama_unavailable_does_not_fail_overall_readiness(client, monkeypatch):
    # M29 Req 4/8: Ollama'nın çökmesi core-api'nin GENEL readiness'ını
    # (postgres/redis'e dayalı) ETKİLEMEMELİ — yalnızca `ai_provider`
    # bloğu "unavailable" göstermeli, üst düzey `status`/HTTP kodu DEĞİL.
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    import requests
    with mock.patch("app.ml.ai_provider.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        resp = client.get("/health/ready")
    body = resp.json()
    assert body["ai_provider"]["provider"] == "ollama"
    assert body["ai_provider"]["status"] == "unavailable"
    # `ai_provider` is reported alongside `checks`, but is not one of its
    # entries — it never feeds the `all_ok` readiness gate (see `checks`
    # containing only infra deps: postgres/redis).
    assert "ai_provider" not in body["checks"]
    assert body["checks"]["postgres"] == "ok"


def test_health_ready_ollama_available_when_reachable(client, monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"models": [{"name": "mistral:latest"}]}

    with mock.patch("app.ml.ai_provider.requests.get", return_value=_FakeResp()):
        resp = client.get("/health/ready")
    assert resp.json()["ai_provider"] == {
        "provider": "ollama", "status": "available", "model": "mistral", "detail": None,
    }


def test_health_ready_does_not_call_llm_generation(client, monkeypatch):
    # Health/readiness ASLA bir üretim çağrısı tetiklememeli — Gemini
    # (`requests.post` via gemini_service) ve Ollama'nın (`requests.post`
    # via rag_service) ikisi de hiç çağrılmamalı.
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    with mock.patch("app.ml.gemini_service._requests.post") as mock_gemini_post, \
         mock.patch("app.ml.rag_service.requests.post") as mock_rag_post:
        client.get("/health/ready")
    mock_gemini_post.assert_not_called()
    mock_rag_post.assert_not_called()
