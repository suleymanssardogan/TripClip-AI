import requests
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """RAG sistemi - Qdrant + Mistral ile travel tips üretimi"""

    def __init__(self):
        self.ollama_url = "http://host.docker.internal:11434"
        self.model = "mistral"
        self._ollama_available: bool = True   # ilk hata sonrası False yapılır
        logger.info("RAGService initialized")

    def _generate(self, prompt: str) -> str:
        """Mistral ile metin üret. Ollama yoksa hızlıca skip et."""
        if not self._ollama_available:
            return ""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=10   # 60s → 10s (Ollama yoksa uzun bekleme anlamsız)
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                logger.warning(f"Ollama error: {response.status_code}")
                return ""
        except Exception as e:
            # Bağlantı hatası → bu session'da Ollama yok, tekrar deneme
            logger.warning(f"Ollama unavailable, RAG devre dışı: {type(e).__name__}")
            self._ollama_available = False
            return ""

    def generate_travel_tips(self, locations: List[Dict]) -> Dict:
        """Lokasyonlar için travel tips üret"""

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
            prompt = f"""Sen bir Türkiye seyahat uzmanısın. 
"{name}" hakkında kısa ve pratik 2 seyahat ipucu ver.
Sadece ipuçlarını yaz, başka açıklama yapma.
Türkçe yaz."""

            tip = self._generate(prompt)
            if tip:
                tips.append({
                    "location": name,
                    "tip": tip.strip()
                })
                logger.info(f"✅ Generated tip for: {name}")

        # Genel özet
        summary_prompt = f"""Sen bir Türkiye seyahat uzmanısın.
Şu yerleri kapsayan kısa bir gezi özeti yaz (3-4 cümle): {locations_text}
Türkçe yaz."""

        summary = self._generate(summary_prompt)
        logger.info(f"✅ Generated summary for {len(tips)} locations")

        return {
            "tips": tips,
            "summary": summary.strip(),
            "locations_covered": location_names
        }