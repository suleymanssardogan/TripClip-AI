"""
Trip Assistant için sağlayıcı-agnostik AI arayüzü (M26, Ollama M28'de eklendi).

Neden yeni bir soyutlama: `GeminiService`/`RAGService` (Ollama) ikisi de
ZATEN var, ama her biri kendi dar görevine kilitli (video'dan lokasyon
çıkarma, travel tips) — HİÇBİRİ genel "bir soruya, verilen bağlamla, metin
cevap üret" şeklinde bir arayüz sunmuyor, ve `TripAssistantService`'in
hangi sağlayıcının çalıştığını bilmesine gerek yok (bkz. milestone'un
kendi "do not expose provider-specific logic" kuralı). Bu yüzden burada
İKİNCİ bir LLM soyutlaması İCAT EDİLMİYOR — `GeminiService`/`RAGService`
zaten kendi sağlayıcılarının soyutlaması; bu dosya yalnızca ikisini (ve
test ortamı için sahte bir sağlayıcıyı) tek, ortak, minimal bir arayüzün
ARKASINA koyuyor.

M26'da kapsam BİLEREK dar tutulmuştu (yalnızca Gemini) — M28, RAGService'in
ZATEN VAR OLAN OLLAMA_URL/OLLAMA_MODEL altyapısını `OllamaAIProvider` ile
AYNI arayüzün arkasına ekliyor. Varsayılan davranış DEĞİŞMEDİ: Gemini hâlâ
varsayılan sağlayıcı, Ollama yalnızca `AI_ASSISTANT_PROVIDER=ollama`
AÇIKÇA ayarlandığında devreye girer.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Sadece erişilebilirlik/model-listesi kontrolü için — GERÇEK bir üretim
# çağrısının (90s) AKSİNE kısa tutulur, çünkü bu /health/ready'nin (ve onu
# çağıran monitoring/orchestration'ın) İSTEK BAŞINA beklediği bir gecikme
# (bkz. M29 Req 5: normal Trip Assistant istek yolu BUNU asla çağırmaz).
_OLLAMA_HEALTH_CHECK_TIMEOUT = 3


class AIProviderError(Exception):
    """Sağlayıcı çağrısı başarısız oldu (ağ/timeout/malformed response) —
    `TripAssistantService` bunu yakalayıp kullanıcıya ham hata/stack trace
    SIZDIRMADAN `AssistantUnavailableException`'a çevirir."""


class AIProvider(ABC):
    """Tek metotluk, kasıtlı minimal arayüz — milestone'un kendi kavramsal
    örneği (`generateResponse(context, message)`) buraya `answer(system_prompt,
    user_message)` olarak uyarlandı."""

    @abstractmethod
    def answer(self, system_prompt: str, user_message: str) -> Dict:
        """Döner: `{"answer": str, "references": [{"day_index": int, "place_id": int}, ...]}`.
        Başarısızlıkta `AIProviderError` fırlatır — asla sessizce boş dönmez
        (çağıranın "cevap yok" ile "sağlayıcı çöktü" durumlarını
        KARIŞTIRMAMASI için — bkz. GeminiService'teki aynı ilke)."""
        ...


class GeminiAIProvider(AIProvider):
    """`GeminiService.answer_question`'ı `AIProvider` arayüzünün arkasına
    koyar — HTTP/retry/JSON-parse mantığının hiçbiri burada TEKRARLANMAZ."""

    def __init__(self, gemini_service):
        self._gemini = gemini_service

    def answer(self, system_prompt: str, user_message: str) -> Dict:
        try:
            return self._gemini.answer_question(system_prompt, user_message)
        except Exception as e:
            raise AIProviderError(str(e)) from e


class OllamaAIProvider(AIProvider):
    """`RAGService.answer_question`'ı `AIProvider` arayüzünün arkasına
    koyar — `GeminiAIProvider`'ın BİREBİR AYNI ilkesi: HTTP/parse
    mantığının hiçbiri burada TEKRARLANMAZ, provider yalnızca ince bir
    adaptör."""

    def __init__(self, rag_service):
        self._rag = rag_service

    def answer(self, system_prompt: str, user_message: str) -> Dict:
        try:
            return self._rag.answer_question(system_prompt, user_message)
        except Exception as e:
            raise AIProviderError(str(e)) from e


class FakeAIProvider(AIProvider):
    """Test/geliştirme sağlayıcısı — AĞ YOK, API anahtarı GEREKMEZ (bkz.
    milestone'un kendi "Tests must NOT require a real LLM call" kuralı).
    Varsayılan olarak deterministik, basit bir yanıt üretir; testler
    `responses`/`error` ile davranışı kontrol edebilir.

    `sequence` (M32, opsiyonel): `responses`'ın (tam metin eşleşmesi
    gerektiren) sözlük tabanlı sürümünün AKSİNE, mesaj İÇERİĞİNDEN
    BAĞIMSIZ olarak sırayla tüketilen bir liste — Trip Assistant'ın araç
    çağrısı döngüsü (bkz. milestone Req 6/15 "provider requests tool →
    tool executes → tool result returned → provider produces final
    answer") gibi ÇOK ADIMLI senaryoları test etmek için: ikinci çağrının
    `user_message`'ı (araç sonucunu İÇEREN, birinci çağrıdan FARKLI bir
    metin) önceden bilinmesi gerekmeden, yalnızca "N. çağrıda ŞUNU dön"
    diye script'lenebilir. İKİNCİ bir test double İCAT ETMEK yerine
    (bkz. milestone'un kendi "do not build a generic agent framework"
    disiplini — test tarafında da aynı sadelik) var olan `FakeAIProvider`
    genişletildi; `sequence` verilmezse (varsayılan `None`) davranış
    M26-31 ile BİREBİR aynı kalır."""

    def __init__(
        self,
        responses: Optional[Dict[str, Dict]] = None,
        error: Optional[Exception] = None,
        sequence: Optional[List[Dict]] = None,
    ):
        self._responses = responses or {}
        self._error = error
        self._sequence = list(sequence) if sequence is not None else None
        self.calls: list = []

    def answer(self, system_prompt: str, user_message: str) -> Dict:
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if self._error:
            raise AIProviderError(str(self._error)) from self._error
        if self._sequence is not None:
            if self._sequence:
                return self._sequence.pop(0)
            return {"answer": f"[fake] {user_message}", "references": []}
        if user_message in self._responses:
            return self._responses[user_message]
        return {"answer": f"[fake] {user_message}", "references": []}


def _configured_provider_name() -> str:
    """`AI_ASSISTANT_PROVIDER`'ı OKUYAN TEK yer — `get_ai_provider()`,
    `get_provider_metadata()` ve `check_provider_health()` (M29) hepsi
    BUNU çağırır, hiçbiri env değişkenini kendi başına ayrıca okumaz
    (bkz. M29 Req 2: "single source of truth" — provider seçimi hâlâ
    yalnızca `get_ai_provider()`'ın kompozisyon sınırında olur, bu
    yardımcı yalnızca AYNI okuma mantığının TEKRARLANMASINI önler)."""
    return os.getenv("AI_ASSISTANT_PROVIDER", "gemini").strip().lower()


def get_ai_provider() -> Optional[AIProvider]:
    """Kompozisyon sınırı — HANGİ sağlayıcının kullanılacağına TEK burada
    karar verilir (bkz. milestone'un kendi "provider selection should
    happen at the composition/configuration boundary" kuralı);
    `TripAssistantService` hangi sağlayıcının çalıştığını asla bilmez.

    `AI_ASSISTANT_PROVIDER` — "gemini" (varsayılan, GERİYE DÖNÜK UYUMLULUK
    için) | "ollama". Bu değişken YENİ; var olan hiçbir deployment'ı
    etkilemez (ayarlanmazsa davranış M26/M27'yle BİREBİR aynı kalır).

    Yapılandırılmış bir sağlayıcı yoksa (anahtar/URL eksik ya da değer
    tanınmıyor) `None` döner — çağıran taraf (`TripAssistantService`) bunu
    `AssistantUnavailableException`'a çevirir, ASLA çökmez ve ASLA
    yapılandırılandan FARKLI bir sağlayıcıya sessizce düşmez."""
    provider_name = _configured_provider_name()

    if provider_name == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            logger.warning("AI_ASSISTANT_PROVIDER=gemini ama GEMINI_API_KEY ayarlanmamış — asistan devre dışı.")
            return None
        from app.ml.gemini_service import GeminiService
        return GeminiAIProvider(GeminiService())

    if provider_name == "ollama":
        if not os.getenv("OLLAMA_URL"):
            logger.warning("AI_ASSISTANT_PROVIDER=ollama ama OLLAMA_URL ayarlanmamış — asistan devre dışı.")
            return None
        from app.ml.rag_service import RAGService
        return OllamaAIProvider(RAGService())

    logger.warning("Bilinmeyen AI_ASSISTANT_PROVIDER değeri: %r — asistan devre dışı.", provider_name)
    return None


# ═════════════════════════════════════════════════════════════════════════
# Provider observability (M29) — `get_ai_provider()`'ın YANINDA, İKİNCİ bir
# provider-seçim mekanizması DEĞİL. `TripAssistantService`/normal Trip
# Assistant istek yolu bu fonksiyonların HİÇBİRİNİ çağırmaz — yalnızca
# `/health/ready` (bkz. app/main.py) ve süreç başlangıcındaki tek seferlik
# log çağırır (bkz. M29 Req 5: "no extra health check per request").
# ═════════════════════════════════════════════════════════════════════════

def get_provider_metadata() -> Dict:
    """Ucuz, YAN ETKİSİZ metadata — ağa hiçbir istek ATMAZ,
    `GeminiService`/`RAGService`'i INSTANTIATE ETMEZ. Yalnızca hangi
    sağlayıcının YAPILANDIRILDIĞINI (ve, Ollama için, hangi modelin)
    rapor eder — sağlayıcının O AN erişilebilir olup olmadığını DEĞİL
    (bkz. `check_provider_health()`).

    Döner: `{"provider": "gemini"|"ollama"|None, "model": str|None}`.
    Tanınmayan/eksik bir değer `provider=None` olarak rapor edilir —
    `get_ai_provider()`'ın None dönmesiyle AYNI "aktif sağlayıcı yok"
    hikâyesi (bkz. Req 3: asla API anahtarı/URL/secret İÇERMEZ)."""
    provider_name = _configured_provider_name()

    if provider_name == "gemini":
        return {"provider": "gemini", "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash")}

    if provider_name == "ollama":
        return {"provider": "ollama", "model": os.getenv("OLLAMA_MODEL", "mistral")}

    return {"provider": None, "model": None}


def check_provider_health() -> Dict:
    """Sağlayıcının O AN erişilebilir olup olmadığını kontrol eder — bunu
    yapan TEK yer, ve yalnızca `/health/ready` bunu çağırır (bkz. M29 Req 5
    ve 6: normal asistan isteği bunu ASLA tetiklemez, gerçek bir üretim
    çağrısı YAPILMAZ, token HARCANMAZ).

    - Gemini: yalnızca YAPILANDIRMA kontrolü (`GEMINI_API_KEY` var mı) —
      GERÇEK bir (ücretli) Gemini çağrısı YAPILMAZ (bkz. Req 7). "healthy"
      burada "yapılandırılmış" anlamına gelir, "canlı doğrulanmış" değil.
    - Ollama: GERÇEK ama HAFİF bir çağrı (`GET /api/tags` — kurulu model
      listesi, `/api/generate` DEĞİL) ile hem erişilebilirlik hem de
      yapılandırılan modelin kurulu olup olmadığı doğrulanır.

    Döner: `{"provider": str|None, "status": str, "model": str|None, "detail": str|None}`
    `status` ∈ `{"configured", "not_configured", "available", "unavailable"}`.
    Asla secret/API anahtarı/Authorization header İÇERMEZ."""
    metadata = get_provider_metadata()
    provider_name = metadata["provider"]
    model = metadata["model"]

    if provider_name is None:
        raw_value = _configured_provider_name()
        return {
            "provider": None, "status": "not_configured", "model": None,
            "detail": f"tanınmayan AI_ASSISTANT_PROVIDER değeri: {raw_value!r}" if raw_value not in ("gemini", "ollama") else None,
        }

    if provider_name == "gemini":
        if os.getenv("GEMINI_API_KEY"):
            return {"provider": "gemini", "status": "configured", "model": model, "detail": None}
        return {"provider": "gemini", "status": "not_configured", "model": model, "detail": "GEMINI_API_KEY ayarlanmamış"}

    # provider_name == "ollama"
    ollama_url = os.getenv("OLLAMA_URL", "").rstrip("/")
    if not ollama_url:
        return {"provider": "ollama", "status": "not_configured", "model": model, "detail": "OLLAMA_URL ayarlanmamış"}

    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=_OLLAMA_HEALTH_CHECK_TIMEOUT)
    except requests.exceptions.RequestException as e:
        logger.warning("Ollama health check: ulaşılamadı (%s)", type(e).__name__)
        return {"provider": "ollama", "status": "unavailable", "model": model, "detail": "Ollama'ya ulaşılamadı"}

    if response.status_code != 200:
        logger.warning("Ollama health check: HTTP %s", response.status_code)
        return {"provider": "ollama", "status": "unavailable", "model": model, "detail": f"Ollama HTTP {response.status_code}"}

    try:
        installed = [m.get("name", "") for m in response.json().get("models", [])]
    except (ValueError, AttributeError):
        installed = []

    # Ollama model adları ":latest" gibi bir etiketle dönebilir (ör.
    # "mistral:latest") — OLLAMA_MODEL="mistral" ile hâlâ EŞLEŞMELİ.
    model_installed = any(m == model or m.split(":")[0] == model for m in installed)
    if not model_installed:
        logger.warning("Ollama health check: yapılandırılan model kurulu değil (%s)", model)
        return {"provider": "ollama", "status": "unavailable", "model": model, "detail": "Yapılandırılan model kurulu değil"}

    return {"provider": "ollama", "status": "available", "model": model, "detail": None}
