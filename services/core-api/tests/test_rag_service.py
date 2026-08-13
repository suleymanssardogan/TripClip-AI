"""
RAGService (Ollama) testleri — `answer_question` (M28, Trip Assistant).
Gerçek bir Ollama'ya hiçbir istek atılmaz; `requests.post` her zaman
mock'lanır. `generate_travel_tips`/`_generate`'in zaten var olan
best-effort (sessizce boş dönen) davranışı bu dosyanın kapsamı DIŞINDA —
yalnızca `answer_question`'ın kendi, hatayı FIRLATAN sözleşmesi test edilir.
"""
from unittest import mock

import pytest
import requests

from app.ml.rag_service import RAGService


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://fake-ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    return RAGService()


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


# ─── Happy path ──────────────────────────────────────────────────────────

def test_answer_question_parses_answer_and_references(service):
    fake_resp = _FakeResponse(json_data={
        "response": '{"answer": "Bugün 4 durağın var.", "references": [{"day_index": 0, "place_id": 25}]}'
    })
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp) as mock_post:
        result = service.answer_question("system prompt", "Bugün nereye gideceğim?")

    assert result == {"answer": "Bugün 4 durağın var.", "references": [{"day_index": 0, "place_id": 25}],
                       "tool_call": None}
    _, kwargs = mock_post.call_args
    # Sistem prompt'un başında ORİJİNAL (paylaşılan, provider-agnostic) metin
    # değişmeden korunur; sonuna yalnızca Ollama'ya özgü JSON-şekli talimatı
    # EKLENİR (bkz. RAGService._JSON_SHAPE_INSTRUCTION — Gemini'nin
    # `responseSchema`'sının Ollama'da bir karşılığı yok, bu yüzden şema
    # burada METİN olarak da belirtiliyor).
    assert kwargs["json"]["system"].startswith("system prompt")
    assert "answer" in kwargs["json"]["system"]
    assert "references" in kwargs["json"]["system"]
    assert "tool_call" in kwargs["json"]["system"]
    assert kwargs["json"]["prompt"] == "Bugün nereye gideceğim?"
    assert kwargs["json"]["format"] == "json"
    assert kwargs["json"]["model"] == "mistral"
    assert kwargs["json"]["stream"] is False
    assert "fake-ollama:11434/api/generate" in mock_post.call_args[0][0]


def test_answer_question_defaults_references_to_empty_list_when_absent(service):
    fake_resp = _FakeResponse(json_data={"response": '{"answer": "Cevap"}'})
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        result = service.answer_question("system", "soru")
    assert result == {"answer": "Cevap", "references": [], "tool_call": None}


def test_answer_question_parses_tool_call_when_present(service):
    # M32 — model bir araç istediğinde "answer" boş, "tool_call" dolu döner.
    fake_resp = _FakeResponse(json_data={
        "response": '{"answer": "", "references": [], "tool_call": {"name": "find_trip_stop", "place_id": 25, "day_index": null}}'
    })
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        result = service.answer_question("system", "Zeugma hangi gün?")
    assert result == {
        "answer": "", "references": [],
        "tool_call": {"name": "find_trip_stop", "place_id": 25, "day_index": None},
    }


def test_answer_question_defaults_answer_to_empty_string_when_key_missing_entirely(service):
    # M33 — "answer" alanı SÖZDİZİMSEL geçerli JSON'da hiç YOKSA (yalnızca
    # boş DEĞİL, TAMAMEN eksikse) çökmemeli — TripAssistantService bunu
    # zaten "boş cevap" yoluyla temiz bir 503'e çevirir.
    fake_resp = _FakeResponse(json_data={"response": '{"references": [{"day_index": 0, "place_id": 1}]}'})
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        result = service.answer_question("system", "soru")
    assert result == {"answer": "", "references": [{"day_index": 0, "place_id": 1}], "tool_call": None}


# ─── Malformed / missing response ───────────────────────────────────────

def test_answer_question_raises_on_malformed_json_response(service):
    fake_resp = _FakeResponse(json_data={"response": "this is not JSON at all"})
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        with pytest.raises(Exception):
            service.answer_question("system", "soru")


def test_answer_question_raises_on_empty_response_text(service):
    fake_resp = _FakeResponse(json_data={"response": ""})
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        with pytest.raises(Exception):
            service.answer_question("system", "soru")


# ─── HTTP / network failures ─────────────────────────────────────────────

def test_answer_question_raises_on_non_200_http_status(service):
    fake_resp = _FakeResponse(status_code=500, text="internal server error")
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        with pytest.raises(Exception):
            service.answer_question("system", "soru")


def test_answer_question_raises_on_missing_model(service):
    # Ollama'nın gerçek "model bulunamadı" davranışı — genellikle 404 +
    # açıklayıcı bir gövde.
    fake_resp = _FakeResponse(status_code=404, text='{"error": "model \'mistral\' not found, try pulling it first"}')
    with mock.patch("app.ml.rag_service.requests.post", return_value=fake_resp):
        with pytest.raises(Exception) as exc_info:
            service.answer_question("system", "soru")
    assert "404" in str(exc_info.value)


def test_answer_question_raises_on_connection_failure(service):
    with mock.patch("app.ml.rag_service.requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        with pytest.raises(Exception):
            service.answer_question("system", "soru")


def test_answer_question_raises_on_timeout(service):
    with mock.patch("app.ml.rag_service.requests.post", side_effect=requests.exceptions.Timeout("timed out")):
        with pytest.raises(Exception):
            service.answer_question("system", "soru")


# ─── Disabled (OLLAMA_URL not set) ───────────────────────────────────────

def test_answer_question_raises_immediately_when_disabled(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    service = RAGService()
    with mock.patch("app.ml.rag_service.requests.post") as mock_post:
        with pytest.raises(Exception):
            service.answer_question("system", "soru")
    mock_post.assert_not_called()  # devre dışıyken ağa hiç gidilmemeli
