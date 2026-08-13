"""
AIProvider soyutlaması birim testleri. AĞ YOK, gerçek bir Gemini/Ollama
çağrısı YAPILMAZ — `FakeAIProvider` ve `GeminiAIProvider`'ın kendi
`GeminiService`'i sahte bir stub ile enjekte edilir. Ollama health-check
testlerinde `requests.get` mock'lanır — GERÇEK ağa hiç gidilmez.
"""
from unittest import mock

import pytest
import requests

from app.ml.ai_provider import (
    AIProviderError,
    FakeAIProvider,
    GeminiAIProvider,
    OllamaAIProvider,
    check_provider_health,
    get_ai_provider,
    get_provider_metadata,
)


# ─── FakeAIProvider ──────────────────────────────────────────────────────────

def test_fake_provider_default_response_reflects_the_message():
    provider = FakeAIProvider()
    result = provider.answer("system", "Bugün nereye gideceğim?")
    assert "Bugün nereye gideceğim?" in result["answer"]
    assert result["references"] == []


def test_fake_provider_records_calls_for_assertions():
    provider = FakeAIProvider()
    provider.answer("sys-prompt", "soru")
    assert provider.calls == [{"system_prompt": "sys-prompt", "user_message": "soru"}]


def test_fake_provider_returns_configured_response_for_a_specific_message():
    provider = FakeAIProvider(responses={
        "Bugün nereye gideceğim?": {"answer": "İlk durağın Antep.", "references": [{"day_index": 0, "place_id": 25}]},
    })
    result = provider.answer("system", "Bugün nereye gideceğim?")
    assert result["answer"] == "İlk durağın Antep."
    assert result["references"] == [{"day_index": 0, "place_id": 25}]


def test_fake_provider_raises_ai_provider_error_when_configured_to_fail():
    provider = FakeAIProvider(error=RuntimeError("boom"))
    with pytest.raises(AIProviderError):
        provider.answer("system", "soru")


# ─── GeminiAIProvider — gerçek GeminiService yerine bir stub enjekte edilir ─

class _StubGeminiService:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = []

    def answer_question(self, system_prompt, user_message):
        self.calls.append((system_prompt, user_message))
        if self._exc:
            raise self._exc
        return self._result


def test_gemini_provider_delegates_to_gemini_service_answer_question():
    stub = _StubGeminiService(result={"answer": "Cevap", "references": []})
    provider = GeminiAIProvider(stub)
    result = provider.answer("sys", "soru")
    assert result == {"answer": "Cevap", "references": []}
    assert stub.calls == [("sys", "soru")]


def test_gemini_provider_wraps_underlying_exceptions_as_ai_provider_error():
    stub = _StubGeminiService(exc=RuntimeError("Gemini 503"))
    provider = GeminiAIProvider(stub)
    with pytest.raises(AIProviderError):
        provider.answer("sys", "soru")


# ─── OllamaAIProvider — gerçek RAGService yerine bir stub enjekte edilir ────
# GeminiAIProvider'ın BİREBİR aynı testleri, farklı stub/sınıf ile.

class _StubRAGService:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = []

    def answer_question(self, system_prompt, user_message):
        self.calls.append((system_prompt, user_message))
        if self._exc:
            raise self._exc
        return self._result


def test_ollama_provider_delegates_to_rag_service_answer_question():
    stub = _StubRAGService(result={"answer": "Cevap", "references": []})
    provider = OllamaAIProvider(stub)
    result = provider.answer("sys", "soru")
    assert result == {"answer": "Cevap", "references": []}
    assert stub.calls == [("sys", "soru")]


def test_ollama_provider_wraps_underlying_exceptions_as_ai_provider_error():
    stub = _StubRAGService(exc=RuntimeError("Ollama bağlantı hatası"))
    provider = OllamaAIProvider(stub)
    with pytest.raises(AIProviderError):
        provider.answer("sys", "soru")


# ─── get_ai_provider() factory — no API key required to import/test ────────

def test_get_ai_provider_returns_none_without_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    assert get_ai_provider() is None


def test_get_ai_provider_returns_gemini_provider_when_api_key_is_set(monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)


def test_get_ai_provider_defaults_to_gemini_when_provider_env_unset(monkeypatch):
    # Geriye dönük uyumluluk: AI_ASSISTANT_PROVIDER hiç ayarlanmamışsa
    # davranış M26/M27'yle BİREBİR aynı kalmalı (varsayılan = gemini).
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)


def test_get_ai_provider_returns_ollama_provider_when_explicitly_selected(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    provider = get_ai_provider()
    assert isinstance(provider, OllamaAIProvider)


def test_get_ai_provider_ollama_selection_ignores_case_and_whitespace(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "  Ollama  ")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    provider = get_ai_provider()
    assert isinstance(provider, OllamaAIProvider)


def test_get_ai_provider_returns_none_for_ollama_without_ollama_url(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    assert get_ai_provider() is None


def test_get_ai_provider_ollama_mode_does_not_require_gemini_api_key(monkeypatch):
    # Ollama açıkça seçildiğinde GEMINI_API_KEY'in eksik olması asistanı
    # BOZMAMALI — sağlayıcılar birbirinden tamamen bağımsız yapılandırılır.
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = get_ai_provider()
    assert isinstance(provider, OllamaAIProvider)


def test_get_ai_provider_gemini_mode_does_not_require_ollama_url(monkeypatch):
    # Ters durum: Gemini seçiliyken (varsayılan ya da açık) OLLAMA_URL'in
    # eksik olması asistanı BOZMAMALI.
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)


def test_get_ai_provider_returns_none_for_unrecognized_provider_value(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    # Geçersiz bir değer, DAHA ÖNCE yapılandırılmış başka bir sağlayıcıya
    # SESSİZCE düşmemeli — açıkça None dönmeli.
    assert get_ai_provider() is None


# ─── get_provider_metadata() — ucuz, YAN ETKİSİZ (M29) ──────────────────────

def test_metadata_reports_gemini_as_active_provider(monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    meta = get_provider_metadata()
    assert meta == {"provider": "gemini", "model": "gemini-2.5-flash"}


def test_metadata_gemini_default_model_when_env_unset(monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    meta = get_provider_metadata()
    assert meta["provider"] == "gemini"
    assert meta["model"]  # bir varsayılan değeri var, boş değil


def test_metadata_reports_ollama_as_active_provider_with_its_model(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:14b")
    meta = get_provider_metadata()
    assert meta == {"provider": "ollama", "model": "qwen2.5:14b"}


def test_metadata_reports_no_provider_for_unrecognized_value(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "openai")
    meta = get_provider_metadata()
    assert meta == {"provider": None, "model": None}


def test_metadata_never_contains_secrets(monkeypatch):
    # Metadata GEMINI_API_KEY/OLLAMA_URL okumaz bile — kazara sızma imkânı yok.
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key-should-never-appear")
    meta = get_provider_metadata()
    assert "super-secret-key-should-never-appear" not in str(meta)
    assert "GEMINI_API_KEY" not in meta
    assert "api_key" not in meta


# ─── check_provider_health() — Gemini: yapılandırma-only ────────────────────

def test_health_gemini_configured_when_api_key_present(monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    result = check_provider_health()
    assert result["provider"] == "gemini"
    assert result["status"] == "configured"


def test_health_gemini_not_configured_without_api_key(monkeypatch):
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = check_provider_health()
    assert result["provider"] == "gemini"
    assert result["status"] == "not_configured"


def test_health_check_never_calls_gemini_generation(monkeypatch):
    # Gemini health, GERÇEK/ücretli bir üretim çağrısı YAPMAMALI — yalnızca
    # env kontrolü. requests.post hiç çağrılmadığını doğrular.
    monkeypatch.delenv("AI_ASSISTANT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    with mock.patch("app.ml.gemini_service._requests.post") as mock_post:
        check_provider_health()
    mock_post.assert_not_called()


# ─── check_provider_health() — Ollama: gerçek ama HAFİF bir çağrı ───────────

class _FakeTagsResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {"models": []}

    def json(self):
        return self._json_data


def test_health_ollama_not_configured_without_url(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    result = check_provider_health()
    assert result["provider"] == "ollama"
    assert result["status"] == "not_configured"


def test_health_ollama_available_when_reachable_and_model_installed(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    fake_resp = _FakeTagsResponse(json_data={"models": [{"name": "mistral:latest"}, {"name": "qwen2.5:7b"}]})
    with mock.patch("app.ml.ai_provider.requests.get", return_value=fake_resp) as mock_get:
        result = check_provider_health()
    assert result["provider"] == "ollama"
    assert result["status"] == "available"
    assert result["model"] == "mistral"
    assert "fake-ollama:11434/api/tags" in mock_get.call_args[0][0]


def test_health_ollama_unavailable_on_connection_failure(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    with mock.patch("app.ml.ai_provider.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        result = check_provider_health()
    assert result["provider"] == "ollama"
    assert result["status"] == "unavailable"


def test_health_ollama_unavailable_on_non_200_status(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    fake_resp = _FakeTagsResponse(status_code=500)
    with mock.patch("app.ml.ai_provider.requests.get", return_value=fake_resp):
        result = check_provider_health()
    assert result["status"] == "unavailable"


def test_health_ollama_unavailable_when_configured_model_not_installed(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    # Ollama erişilebilir ama yalnızca BAŞKA modeller kurulu.
    fake_resp = _FakeTagsResponse(json_data={"models": [{"name": "qwen2.5:7b"}]})
    with mock.patch("app.ml.ai_provider.requests.get", return_value=fake_resp):
        result = check_provider_health()
    assert result["provider"] == "ollama"
    assert result["status"] == "unavailable"
    assert result["model"] == "mistral"


def test_health_ollama_timeout_counts_as_unavailable(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    with mock.patch("app.ml.ai_provider.requests.get", side_effect=requests.exceptions.Timeout("timed out")):
        result = check_provider_health()
    assert result["status"] == "unavailable"


def test_health_check_never_calls_ollama_generation(monkeypatch):
    # Ollama health, GERÇEK bir /api/generate (üretim) çağrısı YAPMAMALI —
    # yalnızca hafif /api/tags. requests.post hiç çağrılmadığını doğrular.
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    fake_resp = _FakeTagsResponse(json_data={"models": [{"name": "mistral"}]})
    with mock.patch("app.ml.ai_provider.requests.get", return_value=fake_resp), \
         mock.patch("app.ml.rag_service.requests.post") as mock_post:
        check_provider_health()
    mock_post.assert_not_called()


def test_health_unrecognized_provider_reports_not_configured(monkeypatch):
    monkeypatch.setenv("AI_ASSISTANT_PROVIDER", "openai")
    result = check_provider_health()
    assert result["provider"] is None
    assert result["status"] == "not_configured"
    assert "openai" in result["detail"]
