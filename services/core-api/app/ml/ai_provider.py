"""
Trip Assistant için sağlayıcı-agnostik AI arayüzü (M26).

Neden yeni bir soyutlama: `GeminiService`/`RAGService` (Ollama) ikisi de
ZATEN var, ama her biri kendi dar görevine kilitli (video'dan lokasyon
çıkarma, travel tips) — HİÇBİRİ genel "bir soruya, verilen bağlamla, metin
cevap üret" şeklinde bir arayüz sunmuyor, ve `TripAssistantService`'in
hangi sağlayıcının çalıştığını bilmesine gerek yok (bkz. milestone'un
kendi "do not expose provider-specific logic" kuralı). Bu yüzden burada
İKİNCİ bir LLM soyutlaması İCAT EDİLMİYOR — `GeminiService`'in kendisi
zaten "Gemini soyutlaması"; bu dosya yalnızca ONU (ve test ortamı için
sahte bir sağlayıcıyı) tek, ortak, minimal bir arayüzün ARKASINA koyuyor.

Kapsam BİLEREK dar tutuldu: yalnızca Gemini gerçek bir sağlayıcı olarak
bağlandı (bkz. docs/trip-assistant.md "Provider scope") — Ollama/RAGService
travel-tips'te olduğu gibi burada da eklenebilir ama bu milestone'da
YAPILMADI (kasıtlı, dokümante edilmiş sadeleştirme, "keep the first
version deliberately scoped").
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional


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


class FakeAIProvider(AIProvider):
    """Test/geliştirme sağlayıcısı — AĞ YOK, API anahtarı GEREKMEZ (bkz.
    milestone'un kendi "Tests must NOT require a real LLM call" kuralı).
    Varsayılan olarak deterministik, basit bir yanıt üretir; testler
    `responses`/`error` ile davranışı kontrol edebilir."""

    def __init__(self, responses: Optional[Dict[str, Dict]] = None, error: Optional[Exception] = None):
        self._responses = responses or {}
        self._error = error
        self.calls: list = []

    def answer(self, system_prompt: str, user_message: str) -> Dict:
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if self._error:
            raise AIProviderError(str(self._error)) from self._error
        if user_message in self._responses:
            return self._responses[user_message]
        return {"answer": f"[fake] {user_message}", "references": []}


def get_ai_provider() -> Optional[AIProvider]:
    """Yapılandırılmış bir sağlayıcı yoksa `None` döner — çağıran taraf
    (`TripAssistantService`) bunu `AssistantUnavailableException`'a çevirir,
    asla çökmez. `USE_GEMINI`/pipeline'ın GEMINI_API_KEY varlığı KENDİSİ
    zaten "etkin mi" sinyali — `GeminiService.__init__` boş bir anahtarla da
    kurulabilir ama gerçek bir çağrıda 401 döner, bu yüzden burada anahtarın
    varlığı AÇIKÇA kontrol edilir."""
    import os
    if os.getenv("GEMINI_API_KEY"):
        from app.ml.gemini_service import GeminiService
        return GeminiAIProvider(GeminiService())
    return None
