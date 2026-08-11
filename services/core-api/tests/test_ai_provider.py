"""
AIProvider soyutlaması birim testleri. AĞ YOK, gerçek bir Gemini/Ollama
çağrısı YAPILMAZ — `FakeAIProvider` ve `GeminiAIProvider`'ın kendi
`GeminiService`'i sahte bir stub ile enjekte edilir.
"""
import pytest

from app.ml.ai_provider import AIProviderError, FakeAIProvider, GeminiAIProvider, get_ai_provider


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


# ─── get_ai_provider() factory — no API key required to import/test ────────

def test_get_ai_provider_returns_none_without_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert get_ai_provider() is None


def test_get_ai_provider_returns_gemini_provider_when_api_key_is_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)
