"""
Gemini 2.0 Flash — multimodal lokasyon çıkarma + travel tips.

SDK KULLANMAZ — sadece `requests` ile direkt REST API.
Yeni paket kurulumu gerekmez, docker build gereksiz.

Kullanım:
  USE_GEMINI=true olduğunda video_processor bu servisi kullanır.
  NER + OCR NER + Vision API + Ollama RAG'ın yerini alır.
  Nominatim geocoding, TSP route, outlier filter tamamen korunur.

Ücretsiz limit (Gemini 2.0 Flash):
  15 RPM · 1500 RPD · 1M TPM
"""
import os
import re
import json
import base64
import logging
import time
from typing import List, Dict, Optional

import requests as _requests

logger = logging.getLogger(__name__)

MAX_FRAMES = 10   # Gemini'ye gönderilecek max frame sayısı
API_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiService:

    def __init__(self):
        self.api_key   = os.getenv("GEMINI_API_KEY", "")
        self.model     = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._endpoint = f"{API_BASE}/{self.model}:generateContent"
        logger.info("GeminiService initialized (model=%s, REST API)", self.model)

    # ─────────────────────────────────────────────────────────────
    # Core HTTP helper
    # ─────────────────────────────────────────────────────────────

    def _call(self, parts: List[Dict], timeout: int = 60, max_retries: int = 3) -> str:
        """Gemini REST API'ye istek at, ham metin döndür.
        503/429 hatalarında otomatik retry (1s → 3s → 7s backoff).
        """
        url  = f"{self._endpoint}?key={self.api_key}"
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature":    0.2,
                "maxOutputTokens": 2048,
            },
        }
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = _requests.post(url, json=body, timeout=timeout)
                if resp.status_code in (429, 500, 503) and attempt < max_retries - 1:
                    # 429 rate limit → daha uzun bekle
                    wait = [15, 30, 60][attempt] if resp.status_code == 429 else [1, 3, 7][attempt]
                    logger.warning("Gemini %d hatası, %ds sonra tekrar deneniyor... (%d/%d)",
                                   resp.status_code, wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (_requests.exceptions.Timeout, _requests.exceptions.ConnectionError) as e:
                last_exc = e
                if attempt < max_retries - 1:
                    wait = [2, 5][min(attempt, 1)]
                    logger.warning("Gemini bağlantı hatası, %ds sonra tekrar: %s", wait, e)
                    time.sleep(wait)
            except Exception as e:
                last_exc = e
                break
        raise last_exc or RuntimeError("Gemini max retry aşıldı")

    # ─────────────────────────────────────────────────────────────
    # Frame yardımcıları
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _frame_part(path: str) -> Optional[Dict]:
        """Frame'i Gemini inline_data part'a çevir."""
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"inline_data": {"mime_type": "image/jpeg", "data": b64}}
        except Exception as e:
            logger.warning("Frame okunamadı %s: %s", path, e)
            return None

    @staticmethod
    def _sample_frames(frames: List[str], n: int = MAX_FRAMES) -> List[str]:
        """Eşit aralıklı n frame seç."""
        if len(frames) <= n:
            return frames
        step = len(frames) / n
        return [frames[int(i * step)] for i in range(n)]

    # ─────────────────────────────────────────────────────────────
    # JSON parse yardımcısı
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """
        Gemini'nin farklı döndürme formatlarını handle eder:
          - Düz JSON
          - ```json ... ``` bloğu içinde
          - Kısmi/bozuk JSON → regex ile { } bloğunu çıkar
        """
        text = raw.strip()

        # 1. ```json ... ``` bloğunu temizle
        if "```" in text:
            parts = text.split("```")
            text = max(parts, key=len).strip()
            if text.startswith("json"):
                text = text[4:].strip()

        # 2. Düz parse dene
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. Regex ile ilk { ... } bloğunu bul (truncated response için)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 4. locations array'ini doğrudan bul
        match = re.search(r'"locations"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if match:
            try:
                return {"locations": json.loads(match.group(1))}
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError("Gemini yanıtı parse edilemedi", text, 0)

    # ─────────────────────────────────────────────────────────────
    # Lokasyon çıkarma
    # ─────────────────────────────────────────────────────────────

    def extract_locations(
        self,
        frames: List[str],
        transcript: str = "",
    ) -> List[Dict]:
        """
        Video frame'leri + ses transkripsiyonundan yer adlarını + koordinatlarını çıkar.

        Döndürür:
          [
            {"name": "Kaputaş Plajı", "lat": 36.19, "lng": 29.69, "type": "beach"},
            {"name": "Bişirici Kebap", "lat": None, "lng": None, "type": "restaurant"},
            ...
          ]
        Koordinat bilinmiyorsa lat/lng = None — uygulama yine de mekanı listeler.
        """
        parts: List[Dict] = []

        sampled = self._sample_frames(frames, MAX_FRAMES)
        loaded  = 0
        for path in sampled:
            part = self._frame_part(path)
            if part:
                parts.append(part)
                loaded += 1

        logger.info("Gemini lokasyon: %d/%d frame yüklendi", loaded, len(sampled))

        transcript_section = (
            f"\n\nSes transkripsiyonu:\n{transcript[:2000]}"
            if transcript and transcript.strip()
            else "\n\nSes transkripsiyonu: Yok"
        )

        prompt_text = (
            "Bu video frame'lerine ve ses transkripsiyonuna bakarak, "
            "videoda geçen TÜM yer isimlerini bul.\n"
            "Dahil et: şehir, ilçe, mahalle, tarihi alan, müze, plaj, şelale, "
            "kanyon, restoran, kafe, otel, çarşı, pazar, doğal güzellik.\n"
            "Dahil ETME: genel sıfatlar (güzel, harika, muhteşem), "
            "sosyal medya kullanıcı adları, hashtag, emoji.\n\n"
            "Her mekan için biliyorsan yaklaşık koordinat ver (lat/lng).\n"
            "Bilmiyorsan null bırak — mekan yine de listeye eklenecek.\n\n"
            "SADECE JSON döndür, başka açıklama yok:\n"
            '{"locations": ['
            '{"name": "Yer Adı", "lat": 37.06, "lng": 37.38, "type": "restaurant"}, '
            '{"name": "Küçük Dükkan", "lat": null, "lng": null, "type": "shop"}'
            "]}"
            + transcript_section
        )
        parts.append({"text": prompt_text})

        try:
            raw  = self._call(parts, timeout=60)
            data = self._parse_json(raw)
            raw_locs = data.get("locations", [])

            # Eski format (string listesi) geriye dönük uyumluluk
            if raw_locs and isinstance(raw_locs[0], str):
                locs = [
                    {"name": l.strip(), "lat": None, "lng": None, "type": "place"}
                    for l in raw_locs if isinstance(l, str) and 3 <= len(l.strip()) <= 80
                ]
            else:
                locs = []
                for item in raw_locs:
                    if not isinstance(item, dict):
                        continue
                    name = (item.get("name") or "").strip()
                    if not (3 <= len(name) <= 80):
                        continue
                    lat = item.get("lat")
                    lng = item.get("lng")
                    # Sayısal doğrulama
                    try:
                        lat = float(lat) if lat is not None else None
                        lng = float(lng) if lng is not None else None
                    except (TypeError, ValueError):
                        lat = lng = None
                    locs.append({
                        "name": name,
                        "lat":  lat,
                        "lng":  lng,
                        "type": item.get("type", "place"),
                    })

            names = [l["name"] for l in locs]
            logger.info("✅ Gemini: %d lokasyon → %s", len(locs), names)
            return locs

        except json.JSONDecodeError:
            logger.warning("Gemini JSON parse hatası, fallback")
            raw_text = raw if 'raw' in dir() else ""
            return [{"name": n, "lat": None, "lng": None, "type": "place"}
                    for n in self._line_fallback(raw_text)]
        except Exception as e:
            logger.error("Gemini extract_locations hatası: %s", e)
            return []

    @staticmethod
    def _line_fallback(text: str) -> List[str]:
        """JSON parse başarısız → önce "name" alanlarını çıkar, yoksa satır satır oku."""
        # Önce "name": "Değer" kalıplarını dene — yeni koordinatlı formatta çalışır
        names = re.findall(r'"name"\s*:\s*"([^"]{3,80})"', text)
        if names:
            return names[:15]

        # Eski string listesi formatı için satır satır
        results = []
        for line in text.splitlines():
            line = line.strip().strip('"-,[]{}:')
            # JSON syntax kalıntılarını filtrele
            if (3 <= len(line) <= 80
                    and not line.startswith(("{", "```", "location", "lat", "lng", "type", "name"))
                    and ":" not in line
                    and line[0].isupper()):
                results.append(line)
        return results[:15]

    # ─────────────────────────────────────────────────────────────
    # Travel tips
    # ─────────────────────────────────────────────────────────────

    def generate_travel_tips(self, locations: List[str]) -> Dict:
        """
        Lokasyon listesinden seyahat ipuçları üret.
        Ollama/Mistral'ın yerini alır — çok daha hızlı ve kaliteli.
        """
        if not locations:
            return {"tips": [], "summary": ""}

        loc_text = ", ".join(locations[:8])
        prompt   = (
            f"Türkiye'deki şu mekanları ziyaret edecek biri için:\n{loc_text}\n\n"
            "Her mekan için 1 kısa pratik ipucu ver (max 2 cümle, Türkçe).\n"
            "Sonunda 2 cümlelik genel gezi özeti ekle.\n\n"
            "SADECE JSON döndür:\n"
            '{"tips": [{"location": "Yer", "tip": "İpucu"}], "summary": "Özet"}'
        )

        try:
            raw  = self._call([{"text": prompt}], timeout=30)
            data = self._parse_json(raw)
            tips = data.get("tips", [])
            summary = data.get("summary", "")
            logger.info("✅ Gemini travel tips: %d ipucu", len(tips))
            return {"tips": tips, "summary": summary}
        except Exception as e:
            logger.error("Gemini travel tips hatası: %s", e)
            return {"tips": [], "summary": ""}
