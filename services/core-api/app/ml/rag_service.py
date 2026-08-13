import json
import os
import requests
import time
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Başarısız olduktan kaç saniye sonra tekrar denensin?
_OLLAMA_RETRY_AFTER = 120  # saniye


class RAGService:
    """RAG sistemi - Qdrant + Ollama (LLM) ile travel tips üretimi.

    Ollama tamamen opsiyoneldir. OLLAMA_URL ayarlanmazsa bu servis
    devre dışı kalır ve generate_travel_tips() boş sonuç döner —
    pipeline'ın geri kalanı etkilenmez.
    """

    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_URL", "").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "mistral")
        self.enabled = bool(self.ollama_url)
        # Sticky bool → timestamp: None = hiç denenmedí / hata yok
        self._ollama_failed_at: Optional[float] = None

        if self.enabled:
            logger.info(f"RAGService initialized — Ollama at {self.ollama_url} (model={self.model})")
        else:
            logger.info("⚠️ RAGService: OLLAMA_URL not set — travel tips generation is disabled (optional feature)")

    def _ollama_available(self) -> bool:
        """Ollama'ya istek atılabilir mi? Son hatadan _OLLAMA_RETRY_AFTER sn geçtiyse tekrar dene."""
        if not self.enabled:
            return False
        if self._ollama_failed_at is None:
            return True
        if time.monotonic() - self._ollama_failed_at >= _OLLAMA_RETRY_AFTER:
            logger.info("Ollama yeniden deneniyor (cooldown doldu)…")
            self._ollama_failed_at = None   # sıfırla, bir şans daha
            return True
        return False

    def _generate(self, prompt: str) -> str:
        """Ollama ile metin üret. Devre dışıysa veya cooldown süresi dolmadıysa skip et."""
        if not self._ollama_available():
            return ""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=90,
            )
            if response.status_code == 200:
                self._ollama_failed_at = None   # başarılı → sıfırla
                return response.json().get("response", "")
            logger.warning("Ollama HTTP %s", response.status_code)
            self._ollama_failed_at = time.monotonic()
            return ""
        except Exception as e:
            logger.warning("Ollama ulaşılamıyor — %ds sonra tekrar denenecek: %s",
                           _OLLAMA_RETRY_AFTER, type(e).__name__)
            self._ollama_failed_at = time.monotonic()
            return ""

    def generate_travel_tips(self, locations: List[Dict]) -> Dict:
        """Lokasyonlar için travel tips üret. Ollama devre dışıysa boş sonuç döner."""

        if not self.enabled:
            return {"tips": [], "summary": ""}

        if not locations:
            return {"tips": [], "summary": ""}

        # Lokasyon listesi oluştur
        location_names = []
        for loc in locations:
            name = loc.get("original_name") or loc.get("name", "")
            if name:
                location_names.append(name)

        if not location_names:
            return {"tips": [], "summary": ""}

        locations_text = ", ".join(location_names)

        # Her lokasyon için tip üret
        tips = []
        for name in location_names[:5]:  # Max 5 lokasyon
            prompt = f'"{name}" için 1 kısa seyahat ipucu ver. Türkçe, max 2 cümle.'

            tip = self._generate(prompt)
            if tip:
                tips.append({
                    "location": name,
                    "tip": tip.strip()
                })
                logger.info(f"✅ Generated tip for: {name}")

        # Genel özet
        summary_prompt = f'Şu Türkiye mekanlarını ziyaret eden biri için 2 cümlelik gezi özeti: {locations_text}. Türkçe.'

        summary = self._generate(summary_prompt)
        logger.info(f"✅ Generated summary for {len(tips)} locations")

        return {
            "tips": tips,
            "summary": summary.strip(),
            "locations_covered": location_names
        }

    # ─────────────────────────────────────────────────────────────
    # Trip Assistant (M28) — serbest-metin soru-cevap, aynı OLLAMA_URL/
    # OLLAMA_MODEL üzerinden. `generate_travel_tips`'in AKSİNE hatayı
    # SESSİZCE YUTMAZ — burada "boş dön" ile "sağlayıcı çöktü" ayrımı
    # önemli (bkz. GeminiService.answer_question'ın AYNI ilkesi; çağıran
    # taraf, `OllamaAIProvider`, bunu `AIProviderError`'a çevirir).
    # ─────────────────────────────────────────────────────────────

    # Ollama'nın `format: "json"` modu Gemini'nin `responseSchema`'sının
    # AKSİNE yalnızca SÖZDİZİMSEL geçerli JSON garantiler — hangi ALAN
    # ADLARININ kullanılacağını ZORLAMAZ. Paylaşılan (`TripAssistantService`
    # içindeki, provider-agnostic) system prompt bu yüzden şema adlarını
    # metin olarak İÇERMEZ (Gemini için gereksiz — o `_ASSISTANT_SCHEMA`
    # parametresiyle zorlanıyor). Gerçek `mistral`/`qwen2.5:7b`/`qwen2.5:14b`
    # ile doğrulandı: bu ek talimat OLMADAN model sözdizimsel geçerli ama
    # YANLIŞ üst-seviye alan adları (`"Aylik Gezisi"`, `"response"`, vb.)
    # üretiyor — bu yüzden bu talimat SADECE Ollama isteğine, burada eklenir.
    # M32: üçüncü, OPSİYONEL bir alan (`tool_call`) eklendi — bkz.
    # app/domain/assistant/tools.py. Ollama'da native/function-calling API'si
    # (`/api/chat` + tools) KULLANILMADI — RAGService zaten `/api/generate`
    # üzerinden çalışıyor ve tool-calling desteği modele/Ollama sürümüne göre
    # ÇOK DEĞİŞKEN; bunun yerine Gemini'yle AYNI, zaten var olan JSON-alan
    # sözleşmesi üçüncü bir alanla genişletildi — iki sağlayıcı da AYNI basit
    # protokolü konuşuyor, provider-özgü bir uyarlayıcı GEREKMEDİ (bkz.
    # docs/trip-assistant.md "Tool calling" — milestone'un kendi "prefer a
    # common internal tool model" izniyle).
    _JSON_SHAPE_INSTRUCTION = (
        "\n\nÇIKTI FORMATI (KESİN KURAL): Yanıtını YALNIZCA şu JSON alanlarıyla ver, "
        'başka HİÇBİR üst-seviye alan adı KULLANMA: "answer", "references", "tool_call".\n'
        '{"answer": "<Türkçe cevabın>", "references": [{"day_index": 0, "place_id": 0}], "tool_call": null}\n'
        '"answer" DAİMA bir string olmalı (bir araç çağırıyorsan boş string "" olabilir). '
        'Referans yoksa "references" alanını boş dizi ([]) olarak bırak. '
        'Bir ARAÇ çağırmak İSTEMİYORSAN "tool_call" alanını null bırak. '
        'Bu üç alan DIŞINDA hiçbir alan EKLEME.'
    )

    def answer_question(self, system_prompt: str, user_message: str) -> Dict:
        """
        Döner: `{"answer": str, "references": [...], "tool_call": {...}|None}`
        (M32 — `tool_call` yeni; her zaman anahtar olarak MEVCUT).

        Ollama'nın `system` alanı (Gemini'nin `systemInstruction`'ıyla AYNI
        rolde: talimatları kullanıcı içeriğinden AYRI tutar) ve
        `format: "json"` modu (Gemini'nin `responseSchema`'sı kadar şemayı
        ZORLAMAZ ama en azından SÖZDİZİMSEL geçerli JSON garantiler)
        kullanılır. Şema alan adları `_JSON_SHAPE_INSTRUCTION` ile METİN
        olarak da EKLENİR (bkz. yukarıdaki not).
        """
        if not self.enabled:
            raise RuntimeError("OLLAMA_URL ayarlanmamış — Ollama sağlayıcısı devre dışı.")

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "system": system_prompt + self._JSON_SHAPE_INSTRUCTION,
                    "prompt": user_message,
                    "stream": False,
                    "format": "json",
                },
                timeout=90,
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama'ya ulaşılamadı: {e}") from e

        if response.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {response.status_code}: {response.text[:200]}")

        raw_text = response.json().get("response", "")
        if not raw_text:
            raise RuntimeError("Ollama boş bir yanıt döndürdü.")

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama yanıtı parse edilemedi: {e}") from e

        return {
            "answer": (data.get("answer") or "").strip(),
            "references": data.get("references") or [],
            "tool_call": data.get("tool_call") or None,
        }