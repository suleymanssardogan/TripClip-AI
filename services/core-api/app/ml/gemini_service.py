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

# extract_locations çıktı sözleşmesinin sürümü. Sözleşme değişince ARTIR —
# cache anahtarlarına girdiği için eski formattaki kayıtlar okunmaz.
#   v1: {"name", "lat", "lng", "type"} listesi
#   v2: {"region": {...}, "locations": [{"name", "type", "city"}]} — koordinat yok
_EXTRACTION_SCHEMA_VERSION = 2

# ─────────────────────────────────────────────────────────────
# Structured output şemaları (Gemini responseSchema — JSON mode)
# ─────────────────────────────────────────────────────────────

# Gemini'den KOORDİNAT İSTENMİYOR — bilerek.
#
# Ölçülen: model yer adlarını çıkarmakta iyi ama konumlarını bilmiyor.
#   · Şanlıurfa'ya ~79 km batıda bir nokta verdi
#   · urfa videosunda beş ayrı mekana AYNI koordinatı verdi (Ciğerci Aziz Usta,
#     Safi Künefe, Gümrük Hanı…) — hepsi şehir merkeziydi
# Bu koordinatlar `gemini_coords` kaynağıyla doğrudan plana giriyordu, yani
# kullanıcı uydurma bir noktaya yönlendiriliyordu.
#
# Yeni sözleşme: Gemini SADECE metin üretir (ad + tür + hangi şehirde).
# Konumu coğrafi veritabanı (Nominatim/Overpass) çözer. Model, aramayı
# yönlendirecek bölge bilgisini verir — bu onun gerçekten bildiği şey.
_LOCATIONS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        # Videonun geçtiği bölge — geocoding'i doğru ülkeye/şehre kilitler.
        # Eskiden bu bilgi Türkiye şehirlerinden oluşan HARDCODE bir listeyle
        # tahmin ediliyordu (video_processor._detect_city_from_list); dünyanın
        # herhangi bir yerinden gelen bir Reels'te o liste hiçbir işe yaramıyordu.
        "region": {
            "type": "OBJECT",
            "properties": {
                "city":         {"type": "STRING", "nullable": True},
                "country":      {"type": "STRING", "nullable": True},
                "country_code": {"type": "STRING", "nullable": True},
            },
        },
        "locations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "type": {"type": "STRING"},
                    # Mekanın bulunduğu şehir/ilçe. Tek videoda birden fazla
                    # şehir gezilebiliyor, o yüzden region.city'ye ek olarak
                    # mekan bazında da soruluyor.
                    "city": {"type": "STRING", "nullable": True},
                },
                "required": ["name"],
            },
        },
    },
    "required": ["locations"],
}

_TRAVEL_TIPS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tips": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "location": {"type": "STRING"},
                    "tip":      {"type": "STRING"},
                },
                "required": ["location", "tip"],
            },
        },
        "summary": {"type": "STRING"},
    },
    "required": ["tips", "summary"],
}


class GeminiService:

    # Celery'nin result_expires (3600s) ile uyumlu — bir task retry edilirse
    # aynı pencerede Gemini'ye tekrar gidip tekrar ücretlendirilmez.
    CACHE_TTL = 3600

    def __init__(self):
        self.api_key   = os.getenv("GEMINI_API_KEY", "")
        self.model     = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._endpoint = f"{API_BASE}/{self.model}:generateContent"
        try:
            from app.core.redis import get_redis
            self._redis = get_redis()
        except Exception:
            self._redis = None
        logger.info("GeminiService initialized (model=%s, REST API)", self.model)

    # ─────────────────────────────────────────────────────────────
    # Idempotency cache — video_id anahtarlı (retry'da tekrar ücretlendirmeyi
    # önler). Sadece BAŞARILI sonuçlar cache'lenir — hata/fallback cache'lenmez,
    # böylece bir retry gerçek bir yeniden deneme şansı bulur.
    # ─────────────────────────────────────────────────────────────

    def _cache_get(self, key: str):
        if not self._redis:
            return None
        try:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def _cache_set(self, key: str, data) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(key, self.CACHE_TTL, json.dumps(data))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # Core HTTP helper
    # ─────────────────────────────────────────────────────────────

    def _call(self, parts: List[Dict], timeout: int = 60, max_retries: int = 3,
              response_schema: Optional[Dict] = None) -> str:
        """Gemini REST API'ye istek at, ham metin döndür.
        503/429 hatalarında otomatik retry (1s → 3s → 7s backoff).

        response_schema verilirse Gemini'nin structured output modu (JSON mode)
        devreye girer — model çıktısı şemaya uymak ZORUNDA, bu da
        `_parse_json`'ın markdown-fence/truncated-JSON kurtarma yollarına
        düşme ihtimalini ortadan kaldırır (üretimde gördüğümüz
        "Gemini JSON parse hatası" fallback'inin kök nedeni).
        """
        # API anahtarı query string'de DEĞİL header'da gider.
        #
        # `?key=...` kullanıldığında requests'in HTTPError mesajı tam URL'yi
        # içeriyor ve anahtar DÜZ METİN olarak loglara düşüyordu (429 hatasında
        # bizzat gözlendi). Bu log Docker stdout'a, oradan da SENTRY_DSN
        # ayarlıysa Sentry'ye gidiyor. Header ile anahtar hiçbir hata
        # mesajında görünmez.
        url = self._endpoint
        generation_config: Dict = {
            # temperature=0 DENENDİ VE GERİ ALINDI.
            #
            # Non-determinizmi çözmek için 0.2'den 0.0'a çekilmişti. Tutarlılık
            # geldi ama DÜŞÜK DEĞERDE sabitlendi — greedy decoding'de model JSON
            # dizisini erken kapatmayı "en olası" buluyor:
            #
            #   antalya-gezilecek-yerler.mp4, aynı dosya, tek fark temperature
            #     0.2 → 9 isim → dedup sonrası 14 mekan
            #     0.0 → 5 isim → dedup sonrası 12 mekan
            #   Kesilen liste ilk 5'in aynısı; kaybolanlar: Çamlık Koyu,
            #   Kaş Halk Plajı, Kaputaş Plajı, Döşemealtı Halı Tarlası.
            #
            # Determinizm artık video içerik hash'iyle cache'ten geliyor
            # (video_processor._gemini_cache_key) — aynı video her zaman aynı
            # sonucu veriyor. Modeli kısıtlamaya gerek yok, o yüzden recall
            # lehine 0.2'ye dönüldü.
            "temperature":    0.2,
            # gemini-2.5-flash varsayılan olarak "thinking" yapıyor ve düşünme
            # token'ları bu bütçeden yeniyor. Eskiden 2048'di; aynı içerikle
            # doğrudan API'ye (bütçe ayarlamadan, yani model varsayılanı
            # 65536 ile) yapılan çağrı 12 lokasyon dönerken pipeline 2
            # dönüyordu. 8192'ye çıkarmak YETMEDİ — ölçüldü, yine 2.
            #
            # DOĞRULANMADI: geriye kalan tek kontrolsüz değişken bütçenin
            # 8192 mi yoksa model varsayılanı mı olduğu. Kullanılmayan token
            # ücretlendirilmediği için bütçeyi cömert tutmanın maliyeti yok.
            "maxOutputTokens": 32768,
        }
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": generation_config,
        }
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = _requests.post(
                    url, json=body, timeout=timeout,
                    headers={"x-goog-api-key": self.api_key},
                )
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
    # Çıktı normalizasyonu
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def normalize_extraction(data) -> Dict:
        """
        Ham Gemini çıktısını (veya cache'ten okunan eski bir kaydı) tek bir
        sözleşmeye indirger:

            {"region": {"city", "country", "country_code"},
             "locations": [{"name", "type", "city"}]}

        Kabul ettiği girdiler:
          · yeni format (dict, region + locations)
          · v1 format (koordinatlı dict listesi) — lat/lng ATILIR
          · düz string listesi (_line_fallback çıktısı)

        Doğrulama tek noktada toplandı: responseSchema ihlal edilse veya
        parse kurtarma yollarından biri devreye girse bile pipeline'a her
        zaman aynı şekil geliyor.
        """
        if isinstance(data, list):
            data = {"locations": data}
        if not isinstance(data, dict):
            data = {}

        raw_region = data.get("region")
        if not isinstance(raw_region, dict):
            raw_region = {}

        def _clean(value, max_len: int = 80) -> Optional[str]:
            if not isinstance(value, str):
                return None
            value = value.strip()
            return value if 0 < len(value) <= max_len else None

        # ISO 3166-1 alpha-2 bekliyoruz; Nominatim'in countrycodes parametresi
        # başka bir şey kabul etmiyor, uydurma bir değer tüm aramaları boşa
        # düşürürdü.
        country_code = _clean(raw_region.get("country_code"), max_len=2)
        region = {
            "city":         _clean(raw_region.get("city")),
            "country":      _clean(raw_region.get("country")),
            "country_code": country_code.lower() if country_code and country_code.isalpha() else None,
        }

        locations: List[Dict] = []
        for item in data.get("locations") or []:
            if isinstance(item, str):
                item = {"name": item}
            if not isinstance(item, dict):
                continue
            name = _clean(item.get("name"))
            if not name or len(name) < 3:
                continue
            locations.append({
                "name": name,
                "type": _clean(item.get("type")) or "place",
                "city": _clean(item.get("city")),
            })

        return {"region": region, "locations": locations}

    # ─────────────────────────────────────────────────────────────
    # Lokasyon çıkarma
    # ─────────────────────────────────────────────────────────────

    def extract_locations(
        self,
        frames: List[str],
        transcript: str = "",
        video_id: Optional[int] = None,
        ocr_texts: Optional[List[str]] = None,
    ) -> Dict:
        """
        Video frame'leri + ses transkripsiyonundan yer ADLARINI çıkar.

        KOORDİNAT DÖNDÜRMEZ (bkz. _LOCATIONS_SCHEMA'daki gerekçe). Bu aşama
        pipeline'ın "çıkarma" adımı; "çözümleme" adımı (isim → gerçek konum)
        PlacesService'in işi.

        Döndürür:
          {
            "region": {"city": "Gaziantep", "country": "Türkiye", "country_code": "tr"},
            "locations": [
              {"name": "Metanet Lokantası", "type": "restaurant", "city": "Gaziantep"},
              {"name": "Elmacı Pazarı",     "type": "market",     "city": "Gaziantep"},
            ],
          }

        video_id verilirse sonuç Redis'e cache'lenir — Celery task retry
        ederse (autoretry_for) aynı video için Gemini'ye tekrar gidip tekrar
        ücretlendirilmez.
        """
        # Cache anahtarına şema sürümü giriyor: sözleşme değiştiğinde eski
        # (koordinatlı, region'sız) çıktılar okunmasın.
        cache_key = f"gemini:locations:v{_EXTRACTION_SCHEMA_VERSION}:{video_id}" if video_id is not None else None
        if cache_key:
            cached = self._cache_get(cache_key)
            if cached is not None:
                logger.info("⚡ Gemini cache hit (locations) video_id=%s", video_id)
                return self.normalize_extraction(cached)

        parts: List[Dict] = []

        # Metin girdisi güçlüyse frame göndermeyi atlayabiliriz — GEMINI_SEND_FRAMES=false.
        # A/B ölçümü için env ile kontrol ediliyor (bkz. aşağıdaki not).
        send_frames = os.getenv("GEMINI_SEND_FRAMES", "true").lower() != "false"

        if send_frames:
            sampled = self._sample_frames(frames, MAX_FRAMES)
            loaded  = 0
            for path in sampled:
                part = self._frame_part(path)
                if part:
                    parts.append(part)
                    loaded += 1
            logger.info("Gemini lokasyon: %d/%d frame yüklendi", loaded, len(sampled))
        else:
            logger.info("Gemini lokasyon: frame gönderilmiyor (GEMINI_SEND_FRAMES=false)")

        transcript_section = (
            f"\n\nSes transkripsiyonu:\n{transcript[:2000]}"
            if transcript and transcript.strip()
            else "\n\nSes transkripsiyonu: Yok"
        )

        # Ekran yazıları — Gemini'ye MUTLAKA metin olarak da verilir.
        #
        # Neden: frame örneklemesi seyrek (95 sn'lik videodan MAX_FRAMES=10, yani
        # ~9,5 sn'de bir kare) ama Reels'teki mekan adı yazıları 2-3 saniye
        # duruyor — Gemini onları çoğu zaman hiç görmüyor. OCR ise çok daha fazla
        # kareyi tarıyor ve adları temiz okuyor ("Metanet Beyran", "TAHMiS
        # KAHVESI", "BAKIRCILAR CARSIS"). Ölçümde bu isimler OCR çıktısında
        # vardı, Gemini sonucunda yoktu; bilgi çıkarılıp çöpe atılıyordu.
        #
        # OCR parçaları bozuk yazılmış olabilir ("GulluogluBaklava",
        # "Elmaci Pazarl") — Gemini'nin dünya bilgisi bunları düzeltebiliyor,
        # bu yüzden ham hâlleriyle veriyoruz.
        ocr_section = ""
        if ocr_texts:
            # Kısa/gürültülü parçaları at, tekrarları tek sefere indir, sırayı koru.
            seen: set = set()
            cleaned: List[str] = []
            for t in ocr_texts:
                t = (t or "").strip()
                if len(t) < 3 or t.lower() in seen:
                    continue
                seen.add(t.lower())
                cleaned.append(t)
            if cleaned:
                joined = " | ".join(cleaned)[:1500]
                ocr_section = (
                    "\n\nEkrandaki yazılar (OCR, yazım hatalı olabilir):\n" + joined
                )

        prompt_text = (
            "Bu video frame'lerine, ekran yazılarına ve ses transkripsiyonuna "
            "bakarak videoda geçen TÜM yer isimlerini bul.\n"
            "Ekran yazıları ve transkript bozuk/eksik yazılmış olabilir "
            "(OCR ve konuşma tanıma hataları) — tanıdığın bir işletme veya "
            "mekan adına benziyorsa DOĞRU yazımıyla ekle.\n"
            "Dahil et: şehir, ilçe, mahalle, tarihi alan, müze, plaj, şelale, "
            "kanyon, restoran, kafe, otel, çarşı, pazar, doğal güzellik.\n"
            "Dahil ETME: genel sıfatlar (güzel, harika, muhteşem), "
            "sosyal medya kullanıcı adları, hashtag, emoji.\n\n"
            "KOORDİNAT VERME. Konumu ayrı bir coğrafi veritabanı çözecek — "
            "senden istenen o aramayı besleyecek DOĞRU METİN.\n"
            "Bu yüzden:\n"
            "- name: mekanın haritada aranabilecek tam ve doğru adı "
            "(kısaltma değil, lakap değil).\n"
            "- city: mekanın bulunduğu şehir/ilçe. Bilmiyorsan null bırak.\n"
            "- region: videonun geçtiği baskın bölge — şehir, ülke ve ISO "
            "3166-1 alpha-2 ülke kodu (tr, es, jp, ge…).\n\n"
            "SADECE JSON döndür, başka açıklama yok:\n"
            '{"region": {"city": "Gaziantep", "country": "Türkiye", "country_code": "tr"}, '
            '"locations": ['
            '{"name": "Metanet Lokantası", "type": "restaurant", "city": "Gaziantep"}, '
            '{"name": "Elmacı Pazarı", "type": "market", "city": "Gaziantep"}'
            "]}"
            + ocr_section
            + transcript_section
        )
        parts.append({"text": prompt_text})

        try:
            raw    = self._call(parts, timeout=60, response_schema=_LOCATIONS_SCHEMA)
            result = self.normalize_extraction(self._parse_json(raw))

            names = [l["name"] for l in result["locations"]]
            logger.info("✅ Gemini: %d lokasyon (bölge: %s) → %s",
                        len(names), result["region"].get("city") or "?", names)
            if cache_key:
                self._cache_set(cache_key, result)
            return result

        except json.JSONDecodeError:
            logger.warning("Gemini JSON parse hatası, fallback")
            raw_text = raw if 'raw' in dir() else ""
            return self.normalize_extraction(
                {"locations": self._line_fallback(raw_text)}
            )
        except Exception as e:
            # Burada []  döndürülüp yutulursa video_processor._safe_run bunu
            # "başarılı, 0 lokasyon" ile ayırt edemez ve degradation raporu
            # yanlış şekilde ✅ OK gösterir (bkz. 2026-07-26 DNS kesintisi
            # olayı). Fırlatarak _safe_run'ın kendi fallback/degradation
            # mekanizmasına devrediyoruz — döndürülen veri yine boş liste
            # olur, tek fark artık doğru şekilde "fallback kullanıldı" olarak
            # işaretlenmesi.
            logger.error("Gemini extract_locations hatası: %s", e)
            raise

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

    def generate_travel_tips(self, locations: List[str], video_id: Optional[int] = None) -> Dict:
        """
        Lokasyon listesinden seyahat ipuçları üret.
        Ollama/Mistral'ın yerini alır — çok daha hızlı ve kaliteli.

        video_id verilirse sonuç Redis'e cache'lenir (bkz. extract_locations).
        """
        if not locations:
            return {"tips": [], "summary": ""}

        cache_key = f"gemini:tips:{video_id}" if video_id is not None else None
        if cache_key:
            cached = self._cache_get(cache_key)
            if cached is not None:
                logger.info("⚡ Gemini cache hit (tips) video_id=%s", video_id)
                return cached

        loc_text = ", ".join(locations[:8])
        prompt   = (
            f"Türkiye'deki şu mekanları ziyaret edecek biri için:\n{loc_text}\n\n"
            "Her mekan için 1 kısa pratik ipucu ver (max 2 cümle, Türkçe).\n"
            "Sonunda 2 cümlelik genel gezi özeti ekle.\n\n"
            "SADECE JSON döndür:\n"
            '{"tips": [{"location": "Yer", "tip": "İpucu"}], "summary": "Özet"}'
        )

        try:
            raw  = self._call([{"text": prompt}], timeout=30, response_schema=_TRAVEL_TIPS_SCHEMA)
            data = self._parse_json(raw)
            tips = data.get("tips", [])
            summary = data.get("summary", "")
            logger.info("✅ Gemini travel tips: %d ipucu", len(tips))
            result = {"tips": tips, "summary": summary}
            if cache_key:
                self._cache_set(cache_key, result)
            return result
        except Exception as e:
            # extract_locations'daki aynı gerekçe: sessizce boş dönmek yerine
            # fırlatarak _safe_run'ın degradation raporunu doğru işaretlemesini
            # sağlıyoruz.
            logger.error("Gemini travel tips hatası: %s", e)
            raise
