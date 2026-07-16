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