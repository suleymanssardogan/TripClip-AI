import requests
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import threading
import time
import json
import redis
import hashlib

logger = logging.getLogger(__name__)

# Türkiye bounding box (lat_min, lon_min, lat_max, lon_max)
TURKEY_BBOX = (35.8, 25.7, 42.1, 44.8)

# ── Dağıtık rate limiter (virtual scheduling) ─────────────────────────────────
#
# Celery worker `--pool=prefork --concurrency=N` ile birden fazla process
# çalıştırdığında, her process'in KENDİ threading.Lock'u sadece o process'i
# throttle eder — N process toplamda N req/sn'ye çıkıp Nominatim/Overpass'ın
# kullanım politikasını ihlal edebilir (IP ban riski). Bu Lua script, tüm
# process'lerin PAYLAŞTIĞI bir Redis key üzerinden "bir sonraki izinli an"ı
# atomik olarak rezerve eder (virtual scheduling) — tek Redis round-trip'i,
# race yok. PX 60000: uzun süre kullanılmazsa key kendiliğinden temizlenir.
_RATE_LIMIT_LUA = """
local next_slot = tonumber(redis.call('GET', KEYS[1]) or '0')
local now = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local my_slot = math.max(now, next_slot)
redis.call('SET', KEYS[1], tostring(my_slot + interval), 'PX', 60000)
return tostring(my_slot)
"""


class PlacesService:
    """Nominatim + Overpass API for location & POI enrichment"""

    # ─────────────────────────────────────────────────────────────
    # Turkish-aware lowercase (Python str.lower() İ→i\u0307 yapar, yanlış!)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def tr_lower(s: str) -> str:
        return s.replace("İ", "i").replace("I", "ı").lower()

    @staticmethod
    def ascii_fold(s: str) -> str:
        return (s.replace("ğ", "g").replace("ü", "u").replace("ş", "s")
                 .replace("ı", "i").replace("ö", "o").replace("ç", "c")
                 .replace("â", "a").replace("î", "i").replace("û", "u"))

    # Overpass fallback zinciri — ilk cevap veren kullanılır
    # kumi.systems öne alındı: overpass-api.de genellikle yavaş/meşgul
    _OVERPASS_ENDPOINTS = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    def __init__(self):
        self.nominatim_url = "https://nominatim.openstreetmap.org"
        # Aktif Overpass endpoint — başarısız olunca bir sonrakine geçer
        self._overpass_endpoint_idx = 0
        self.headers = {
            "User-Agent": "TripClip-AI/1.0 (educational project)"
        }
        # Overpass rate limiter — community service, max 1 req/3s
        self._overpass_min_interval: float = 3.0
        # Nominatim rate limiter — usage policy, max 1 req/s
        self._nominatim_min_interval: float = 1.0
        # enrich_locations lokasyonları paralel işlerken Nominatim/Overpass'a
        # istek GÖNDERME anını (yanıt beklemeyi değil) throttle etmek için —
        # birden fazla thread/process aynı anda rate limit penceresine girmesin.
        # Redis erişilemezse (bağlantı koptu) process-içi fallback için kullanılır.
        self._rate_lock = threading.Lock()
        self._local_next_slot: dict = {}
        # Sticky bool → timestamp tabanlı retry. Process-içi fallback; asıl
        # durum Redis'te tutulur (bkz. _overpass_circuit_open).
        self._overpass_failed_at: Optional[float] = None
        # İlk timeout'dan sonra bu süre boyunca Overpass'ı hiç deneme.
        self._overpass_retry_after: float = 600.0
        try:
            # REDIS_URL (auth dahil) — hardcoded host/port kullanmak production'da
            # Redis şifre istediğinde sessizce bağlantı hatasına yol açıyordu, bu
            # da dağıtık rate limiter'ın (_throttle) fark edilmeden process-içi
            # fallback'e düşmesine sebep oluyordu.
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            self.cache = redis.Redis.from_url(redis_url, decode_responses=True)
            self.cache.ping()
            self.cache_ttl = 60 * 60 * 24 * 7
            logger.info("✅ Redis cache connected")
        except Exception as e:
            self.cache = None
            logger.warning(f"⚠️ Redis unavailable: {e}")

    # ─────────────────────────────────────────────────────────────
    # Dağıtık rate limiter
    # ─────────────────────────────────────────────────────────────

    def _throttle(self, key: str, interval: float) -> None:
        """İstek gönderme anını throttle eder.

        Redis varsa dağıtık (tüm worker process'leri arasında toplam hızı
        sınırlar, bkz. _RATE_LIMIT_LUA) — yoksa process-içi fallback'e düşer
        (tek process'te hâlâ doğru, çoklu process'te sadece politeness
        garantisi zayıflar, hiçbir zaman çökmez).
        """
        now = time.time()
        if self.cache:
            try:
                my_slot = float(self.cache.eval(_RATE_LIMIT_LUA, 1, key, now, interval))
                wait = my_slot - now
                if wait > 0:
                    time.sleep(wait)
                return
            except Exception as exc:
                logger.debug("Redis rate limiter kullanılamadı (%s), process-içi fallback: %s", key, exc)

        with self._rate_lock:
            last_slot = self._local_next_slot.get(key, 0.0)
            wait = last_slot - now
            if wait > 0:
                time.sleep(wait)
            self._local_next_slot[key] = max(now, last_slot) + interval

    # ─────────────────────────────────────────────────────────────
    # Overpass devre kesici (circuit breaker)
    # ─────────────────────────────────────────────────────────────
    #
    # Overpass endpoint'lerinin üçü de sürekli timeout veriyor (Türkiye
    # bbox'ında regex isim araması çok pahalı bir sorgu). Devre kesici
    # eskiden yalnızca instance alanındaydı; PlacesService her videoda
    # yeniden kurulduğu için her video 3 endpoint × timeout kadar —
    # ölçtüğümüzde ~28 saniye — boşa bekliyordu ve sıfır sonuç dönüyordu.
    # Durumu Redis'e taşıyınca ilk başarısızlıktan sonraki tüm videolar
    # Overpass'ı hiç denemeden geçiyor.

    _OVERPASS_CIRCUIT_KEY  = "circuit:overpass:open"
    # "open" süresi dolduğunda tamamen sağlıklı varsaymamak için — Overpass
    # bir kez düştüyse bir sonraki deneme UCUZ olmalı (tek endpoint, kısa
    # timeout). Bu bayrak olmadan cooldown her dolduğunda bir video yeniden
    # 3 endpoint × 8s = ~25s ödüyordu.
    _OVERPASS_DEGRADED_KEY = "circuit:overpass:degraded"
    _OVERPASS_DEGRADED_TTL = 24 * 3600
    _OVERPASS_PROBE_TIMEOUT = 3.0

    def _overpass_circuit_open(self) -> bool:
        """Devre açık mı (yani Overpass'ı hiç denememeli miyiz)?"""
        if self.cache:
            try:
                if self.cache.get(self._OVERPASS_CIRCUIT_KEY):
                    return True
            except Exception:
                pass  # Redis yoksa aşağıdaki process-içi kontrole düş

        if self._overpass_failed_at is None:
            return False
        return (time.time() - self._overpass_failed_at) < self._overpass_retry_after

    def _overpass_probe_mode(self) -> bool:
        """
        Yarı-açık durum: devre kapandı ama Overpass yakın geçmişte düşmüştü.
        Tek endpoint'e kısa timeout'la yoklama yaparız; başarısızsa devre
        hemen yeniden açılır, başarılıysa tamamen iyileşmiş sayılır.
        """
        if not self.cache:
            return self._overpass_failed_at is not None
        try:
            return bool(self.cache.get(self._OVERPASS_DEGRADED_KEY))
        except Exception:
            return self._overpass_failed_at is not None

    def _trip_overpass_circuit(self) -> None:
        """Devreyi aç — `_overpass_retry_after` boyunca Overpass denenmez."""
        self._overpass_failed_at = time.time()
        if self.cache:
            try:
                self.cache.setex(self._OVERPASS_CIRCUIT_KEY,
                                 int(self._overpass_retry_after), "1")
                self.cache.setex(self._OVERPASS_DEGRADED_KEY,
                                 self._OVERPASS_DEGRADED_TTL, "1")
            except Exception:
                pass

    def _reset_overpass_circuit(self) -> None:
        """Başarılı yanıt geldi — Overpass tamamen sağlıklı say."""
        self._overpass_failed_at = None
        if self.cache:
            try:
                self.cache.delete(self._OVERPASS_CIRCUIT_KEY,
                                  self._OVERPASS_DEGRADED_KEY)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # Cache helpers
    # ─────────────────────────────────────────────────────────────

    def _cache_key(self, prefix: str, text: str) -> str:
        return f"{prefix}:{hashlib.md5(text.lower().strip().encode()).hexdigest()}"

    def _cache_get(self, key: str) -> Optional[Dict]:
        if not self.cache:
            return None
        try:
            raw = self.cache.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            # Negatif sonuç sentinel — "bulunamadı" olarak cache'lendi
            if isinstance(data, dict) and data.get("__not_found__"):
                return {"__not_found__": True}
            return data
        except Exception:
            return None

    def _cache_set(self, key: str, data: Dict):
        if not self.cache:
            return
        try:
            self.cache.setex(key, self.cache_ttl, json.dumps(data))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # Nominatim — şehir / büyük yer araması
    # ─────────────────────────────────────────────────────────────

    def search_place(self, location_name: str, country: str = "Turkey",
                     city_bbox: Optional[Tuple] = None,
                     city_hint: Optional[str] = None,
                     country_code: Optional[str] = None) -> Optional[Dict]:
        """
        Nominatim ile yer ara.
        city_bbox verilirse Nominatim'in viewbox/bounded özelliği devreye girer:
        sadece o bbox içindeki sonuçlar döner — manuel mesafe hesabına gerek kalmaz.

        TripClip artık dünyanın her yerinden (Instagram Reels) video işleyebiliyor,
        bu yüzden ülke kısıtlaması varsayılan olarak KAPALI (country_code=None) —
        yabancı yer isimleri (örn. "Budapeşte") sadece Türkiye'ye kısıtlanınca hiç
        bulunamıyordu. country_code verilirse (örn. bir çağıran özellikle Türkiye
        içeriği için biliyorsa) Nominatim'e iletilir; Türkiye önceliği zaten
        city_hint/mesafe puanlamasıyla (aşağıda) sağlanıyor.

        Nominatim kalite iyileştirmeleri:
          - bounded=1 + viewbox → bbox varsa bölgeye kilitlenir
          - limit=10 + en iyi eşleşme seçimi → akıllı puanlama (city_hint & mesafe) ile
        """
        # Cache key: bbox ve hint bağlamını da dahil et (farklı şehir/hint = farklı sonuç)
        bbox_suffix = f"|{city_bbox}" if city_bbox else ""
        hint_suffix = f"|{city_hint}" if city_hint else ""
        cc_suffix = f"|{country_code}" if country_code else ""
        key = self._cache_key("nom", location_name + bbox_suffix + hint_suffix + cc_suffix)
        cached = self._cache_get(key)
        if cached:
            if cached.get("__not_found__"):
                return None   # negatif cache — Nominatim çağrısı yapma
            logger.info(f"⚡ Nominatim cache hit: {location_name}")
            return cached

        try:
            # Rate limiter: Nominatim usage policy — istek gönderme anını
            # (yanıt beklemeyi değil) throttle et; Redis üzerinden dağıtık
            # olduğu için birden fazla worker process'i olsa da toplamda 1 req/s
            # korunur (bkz. _throttle).
            self._throttle("ratelimit:nominatim", self._nominatim_min_interval)
            params: dict = {
                "q":            location_name,   # country ayrı parametre olarak
                "format":       "json",
                "limit":        10,              # en iyi 10 → akıllı filtreleme için
                "addressdetails": 1,
            }
            if country_code:
                params["countrycodes"] = country_code
            # Bbox varsa Nominatim'e ver — yabancı şehirleri kendisi atar
            if city_bbox:
                lat_min, lon_min, lat_max, lon_max = city_bbox
                params["viewbox"] = f"{lon_min},{lat_max},{lon_max},{lat_min}"
                params["bounded"] = 1

            resp = requests.get(
                f"{self.nominatim_url}/search",
                params=params,
                headers=self.headers, timeout=10
            )
            if resp.status_code != 200:
                # Geçici hata (429/5xx) — "bulunamadı" olarak cache'leme, sadece dön.
                return None
            if not resp.json():
                self._cache_set(key, {"__not_found__": True})
                return None

            results = resp.json()
            
            # En iyi adayı puanlayarak seç
            best_place = None
            best_score = (-1, -1, -1.0)  # (prov_match, geo_consistent, importance)

            center_lat, center_lng = None, None
            if city_bbox:
                center_lat = (city_bbox[0] + city_bbox[2]) / 2
                center_lng = (city_bbox[1] + city_bbox[3]) / 2

            for p in results:
                try:
                    lat_val = float(p.get("lat", 0))
                    lon_val = float(p.get("lon", 0))
                except (ValueError, TypeError):
                    continue

                importance = float(p.get("importance", 0) or 0)
                
                # 1. İl/şehir eşleşmesi (city_hint ile)
                prov_match = 0
                if city_hint:
                    hint_l = self.tr_lower(city_hint.strip())
                    hint_fold = self.ascii_fold(hint_l)
                    addr = p.get("address", {})
                    for key_field in ("province", "state", "city", "town", "county"):
                        val = addr.get(key_field)
                        if val:
                            val_l = self.tr_lower(val.strip())
                            val_fold = self.ascii_fold(val_l)
                            if hint_fold in val_fold or val_fold in hint_fold:
                                prov_match = 1
                                break

                # 2. Coğrafi tutarlılık (180 km mesafe)
                geo_consistent = 1
                if center_lat is not None and center_lng is not None:
                    dist = self._haversine_km(center_lat, center_lng, lat_val, lon_val)
                    if dist > 180.0:
                        geo_consistent = 0

                score = (prov_match, geo_consistent, importance)
                if score > best_score:
                    best_score = score
                    best_place = p

            if not best_place:
                self._cache_set(key, {"__not_found__": True})
                return None

            place = best_place
            data = {
                "name":            place.get("display_name"),
                "place_id":        place.get("place_id"),
                "osm_id":          place.get("osm_id"),
                "osm_type":        place.get("osm_type"),
                "address":         place.get("display_name"),
                "location":        {"lat": float(place["lat"]), "lng": float(place["lon"])},
                "type":            place.get("type"),
                "class":           place.get("class"),
                "importance":      place.get("importance"),
                "address_details": place.get("address", {}),
            }
            self._cache_set(key, data)
            return data

        except Exception as e:
            logger.error(f"Nominatim error for '{location_name}': {e}")
            return None

    # ─────────────────────────────────────────────────────────────
    # Overpass — kafe / restoran / işletme araması
    # ─────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────
    # Mesafe hesaplama (Haversine)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    def _within_city_area(self, place_data: Dict,
                          city_center: Optional[Tuple[float, float]],
                          max_km: float = 180) -> bool:
        """
        Bulunan yer şehir merkezine max_km içinde mi?
        city_center yoksa → her zaman True (filtreleme yok).
        Bu filtre yanlış şehirdeki eşleşmeleri atar:
          'Halk Plaj' → İstanbul (850km uzak) → reddedilir
          'Kaputaş Plajı' → Kaş/Antalya (100km) → kabul edilir
        """
        if not city_center:
            return True
        loc = place_data.get("location")
        if not loc:
            return True
        km = self._haversine_km(city_center[0], city_center[1],
                                loc["lat"], loc["lng"])
        if km > max_km:
            logger.info(f"🚫 Uzak yer atlandı ({km:.0f}km > {max_km}km): "
                        f"{place_data.get('name')}")
        return km <= max_km

    def search_poi_overpass(self, name: str,
                             bbox: Tuple = TURKEY_BBOX) -> Optional[Dict]:
        """
        Overpass API ile OSM'de işletme/mekan ara.
        Nominatim'in bulamadığı kafeler, restoranlar, tarihi alanlar için.
        """
        key = self._cache_key("ovp", name)
        cached = self._cache_get(key)
        if cached:
            if cached.get("__not_found__"):
                return None   # negatif cache — Overpass çağrısı yapma
            logger.info(f"⚡ Overpass cache hit: {name}")
            return cached

        # Overpass QL — name'i fuzzy eşleştir
        lat_min, lon_min, lat_max, lon_max = bbox
        # Plaj, şelale, doğa alanları için natural/waterway da ekle
        query = f"""
[out:json][timeout:10];
(
  nwr["name"~"{name}",i]["amenity"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["tourism"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["historic"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["leisure"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["natural"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["waterway"]({lat_min},{lon_min},{lat_max},{lon_max});
  nwr["name"~"{name}",i]["shop"]({lat_min},{lon_min},{lat_max},{lon_max});
);
out center 3;
"""
        try:
            # Devre açıksa hiç deneme — videolar ve worker'lar arasında paylaşılır.
            if self._overpass_circuit_open():
                logger.debug("Overpass devresi açık, atlanıyor: '%s'", name)
                return None

            # Round-robin başlangıç endpoint'i — her çağrı bir sonraki endpoint'ten
            # başlar. Aşağıda her endpoint KENDİ throttle key'iyle bekletildiği için
            # (3 bağımsız sunucu, bağımsız rate limit pencereleri) efektif Overpass
            # limiti tek-endpoint'e göre ~3 kat artar (1 req/3s → ~1 req/s toplam).
            n_endpoints = len(self._OVERPASS_ENDPOINTS)
            with self._rate_lock:
                start_idx = self._overpass_endpoint_idx
                self._overpass_endpoint_idx = (start_idx + 1) % n_endpoints

            # Yarı-açık yoklama: tek endpoint, kısa timeout. Overpass hâlâ
            # ölüyse maliyet 3s (25s değil); ayaktaysa devre tamamen kapanır.
            probing = self._overpass_probe_mode()
            if probing:
                attempts, req_timeout = 1, self._OVERPASS_PROBE_TIMEOUT
                logger.info("Overpass yoklaması (tek endpoint, %.0fs)…", req_timeout)
            else:
                attempts, req_timeout = n_endpoints, 8

            # Fallback endpoint zinciri — ilk cevap veren kazanır
            resp = None
            for attempt in range(attempts):
                idx = (start_idx + attempt) % n_endpoints
                url = self._OVERPASS_ENDPOINTS[idx]
                # Rate limiter: her endpoint bağımsız — min 3s arayla, Redis
                # üzerinden dağıtık (bkz. _throttle).
                self._throttle(f"ratelimit:overpass:{idx}", self._overpass_min_interval)
                try:
                    resp = requests.post(url, data={"data": query},
                                         headers=self.headers, timeout=req_timeout)
                    if resp.status_code == 200:
                        break
                    if resp.status_code == 429:
                        time.sleep(3)
                except requests.exceptions.Timeout:
                    logger.warning("Overpass timeout: %s — sonraki endpoint deneniyor", url)
                    continue
                except Exception:
                    continue

            if resp is None or resp.status_code != 200:
                logger.warning("Overpass: tüm endpointler başarısız '%s' — devre %ds açılıyor",
                               name, int(self._overpass_retry_after))
                self._trip_overpass_circuit()
                return None

            # Buraya geldiysek Overpass yanıt verdi — devreyi tamamen kapat.
            self._reset_overpass_circuit()

            elements = resp.json().get("elements", [])
            if not elements:
                logger.info(f"Overpass: no results for '{name}'")
                # Negatif sonucu kısa TTL ile cache'le → aynı isim tekrar gelirse 1s uyuma
                self._cache_set(key, {"__not_found__": True})
                return None

            # En iyi eşleşmeyi seç (tam isim eşleşmesi önce)
            best = None
            name_lower = name.lower()
            for el in elements:
                tags = el.get("tags", {})
                el_name = tags.get("name", "").lower()
                if name_lower in el_name or el_name in name_lower:
                    best = el
                    break
            if best is None:
                best = elements[0]

            tags = best.get("tags", {})
            # Koordinat al (node direkt, way/relation → center)
            if best["type"] == "node":
                lat, lng = best["lat"], best["lon"]
            else:
                center = best.get("center", {})
                lat, lng = center.get("lat"), center.get("lon")

            if not lat or not lng:
                return None

            osm_class = tags.get("amenity") or tags.get("tourism") or \
                        tags.get("historic") or tags.get("leisure") or \
                        tags.get("shop") or "place"
            display_name = tags.get("name", name)
            addr_parts = [
                tags.get("addr:street", ""),
                tags.get("addr:city", ""),
                tags.get("addr:country", "Türkiye"),
            ]
            address = ", ".join(p for p in addr_parts if p) or display_name

            data = {
                "name":       display_name,
                "address":    address,
                "location":   {"lat": lat, "lng": lng},
                "type":       osm_class,
                "class":      self._overpass_class(tags),
                "importance": 0.15,   # sabit — işletme = makul önem
                "source":     "overpass",
            }
            data["category"] = self._categorize(data["class"], data["type"])
            self._cache_set(key, data)
            logger.info(f"✅ Overpass found: {display_name} ({lat},{lng})")
            return data

        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ("NameResolutionError", "Failed to resolve",
                                           "ConnectionError", "NewConnectionError")):
                logger.warning("Overpass DNS/network hatası — %ds sonra tekrar denenecek: %s",
                               int(self._overpass_retry_after), e)
                self._trip_overpass_circuit()
            else:
                logger.error("Overpass hatası '%s': %s", name, e)
            return None

    def _overpass_class(self, tags: Dict) -> str:
        if tags.get("amenity"):   return "amenity"
        if tags.get("tourism"):   return "tourism"
        if tags.get("historic"):  return "historic"
        if tags.get("leisure"):   return "leisure"
        if tags.get("shop"):      return "shop"
        return "place"

    # ─────────────────────────────────────────────────────────────
    # Ana enrichment — tüm lokasyonları zenginleştir
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _restore_ocr_turkish(name: str) -> Optional[str]:
        """
        OCR Latin→Türkçe karakter düzeltmesi.
        RapidOCR (Latin model): ş→s, ğ→g, ö→o, ü→u, ı→i veya l
        Sadece yer isimlerinde çok geçen kalıplara dokunur — false positive riski düşük.
        """
        result = name

        # ── 1. Suffix düzeltmeleri (yüksek güven) ─────────────────────────
        suffix_fixes = [
            # Türkçe iyelik ekleri: "Plajl" / "Plaji" → "Plajı"
            ("Plajl",    "Plajı"),   ("plajl",    "plajı"),
            ("Plaji",    "Plajı"),   ("plaji",    "plajı"),
            # "Tarlasl" → "Tarlası"
            ("Tarlasl",  "Tarlası"), ("tarlasl",  "tarlası"),
            # "Hali " → "Halı " (karpet/tarla isimlerinde)
            ("Hali ",    "Halı "),   ("hali ",    "halı "),
        ]
        for bad, good in suffix_fixes:
            result = result.replace(bad, good)

        # ── 2. Kelime bazlı düzeltmeler (sık geçen yer isimleri) ──────────
        word_map = {
            "goynuk":    "Göynük",
            "goynak":    "Göynük",
            "camlik":    "Çamlık",
            "camli":     "Çamlı",
            "magarali":  "Mağaralı",
            "magara":    "Mağara",
            "kalekoy":   "Kaleköy",
            "kaleici":   "Kaleiçi",
            "selalesi":  "Şelalesi",
            "selale":    "Şelale",
            "gozu":      "Gözü",
            "gozlu":     "Gözlü",
            "hidayet":   "Hidayet",   # zaten doğru, değiştirme
        }
        words = result.split()
        new_words = [word_map.get(w.lower(), w) for w in words]
        result = " ".join(new_words)

        return result if result != name else None

    def _ocr_fallback_variants(self, name: str) -> List[str]:
        """
        OCR hatalarına karşı varyantlar üretir:
          1. Sondaki yanlış karakter kaldırma (Mağaral → Mağara)
          2. İlk / son kelime yalnız deneme
          3. C↔G başlangıç karışıklığı
          4. Turkish OCR char restoration (ş←s, ğ←g, ö←o, ü←u, ı←l)
        """
        # Turkish restore zaten enrich_locations'da pre-processing olarak yapılıyor.
        # Burada sadece 2 minimal varyant: trailing char + ilk kelime.
        # 4 varyant → 4 Nominatim/Overpass çağrısı = çok yavaş; 2 varyant yeterli.
        words = name.split()
        variants: List[str] = []

        # 1. Son karakteri at (trailing OCR artifact: "l", "i", "1")
        last = words[-1]
        if len(last) > 4:
            variants.append(" ".join(words[:-1] + [last[:-1]]))

        # 2. Sadece ilk kelime (genellikle asıl yer ismi — en bilgilendirici kısım)
        if len(words) > 1 and len(words[0]) > 3:
            variants.append(words[0])

        # Orijinali tekrarlama
        return [v for v in variants if v.lower() != name.lower()]

    def enrich_locations(self, locations: List[str],
                         use_overpass: bool = False,
                         city_bbox: tuple = None,
                         city_hint: Optional[str] = None,
                         country_code: Optional[str] = None) -> List[Dict]:
        """
        Lokasyon listesini zenginleştir.
        use_overpass=True → Nominatim bulamazsa Overpass'ı dene.
        city_bbox verilmişse merkezi bul → uzak yerleri filtrele (yanlış şehir eşleşmesi).
        country_code: yalnızca çağıran içeriğin belli bir ülkeyle sınırlı olduğunu
        biliyorsa verilir (örn. "tr"); varsayılan None → dünya genelinde arar.
        """
        if not locations:
            return []

        # city_bbox'tan şehir merkezi koordinatı çıkar (validasyon için)
        city_center: Optional[Tuple[float, float]] = None
        if city_bbox:
            city_center = (
                (city_bbox[0] + city_bbox[2]) / 2,   # orta lat
                (city_bbox[1] + city_bbox[3]) / 2,   # orta lon
            )

        # Tek başına tip kelimesi olan girişleri filtrele
        # ("Koyu", "Plaj" gibi kelimeler NER pipeline'ından da gelebilir)
        _generic_words = {
            "koyu", "koy", "köy", "plaj", "plajı", "sahil", "dağ", "göl", "gol",
            "şelale", "selale", "orman", "vadi", "tepe", "kale", "ada", "liman",
        }

        # ── Tek bir lokasyonu zenginleştir (Nominatim/Overpass I/O burada) ──
        #
        # Ağdan gelen 1-4 adımlık waterfall her lokasyon için sıralı kalır
        # (adım 2 ancak adım 1 başarısızsa anlamlı), ama LOKASYONLAR ARASI
        # artık paralel çalışır — önceden tamamen seri olan bu döngü, video
        # başına 10-15 lokasyon için 15-45+ saniye sürebiliyordu.
        #
        # NOT: orijinal seri koddaki davranış aynen korunuyor — adım 3 (OCR
        # varyantı) bir eşleşme bulup eklese bile adım 4 (şehir qualifier)
        # yine de denenir ve o da eşleşirse AYRI bir kayıt daha eklenir; bu
        # yüzden bu fonksiyon tek dict değil, 0-2 elemanlı bir liste döner.
        def _process_one(location: str) -> List[Dict]:
            results: List[Dict] = []

            if location.startswith("##") or len(location) < 3:
                return results
            if location.endswith(("-", "?", "'")):
                return results

            # Generic tek kelime → yer ismi değil, atla
            if self.tr_lower(location.strip()) in _generic_words:
                logger.debug(f"Generic kelime atlandı: '{location}'")
                return results

            # ALL-CAPS OCR metni → ilk kelimeyi al (genellikle yer ismi başı)
            # Son kelimeyi almıyoruz: "AZIANTEP DIS" → "Dis" (havalimanı) yanlış eşleşmesi.
            # Şehir tespiti için fuzzy match: "AZIANTEP" → "Gaziantep"
            if location.isupper():
                words_caps = location.split()
                # Fuzzy şehir tespiti: "AZIANTEP" → "Gaziantep"
                _tr_cities = {
                    "gaziantep", "antalya", "istanbul", "ankara", "izmir", "bursa",
                    "adana", "konya", "mersin", "kayseri", "eskisehir", "trabzon",
                    "diyarbakir", "samsun", "malatya", "kahramanmaras", "erzurum",
                }
                city_match = None
                for w in words_caps:
                    wl = w.lower()
                    for city in _tr_cities:
                        ratio = SequenceMatcher(None, wl, city).ratio()
                        if ratio >= 0.82 and abs(len(wl) - len(city)) <= 2:
                            city_match = city.title()
                            break
                    if city_match:
                        break
                if city_match:
                    location = city_match
                    logger.info(f"🏙️ ALL-CAPS şehir tespiti: '{location}' → '{city_match}'")
                else:
                    # Şehir bulunamazsa ilk kelimeyi al (en az 5 karakter)
                    first = words_caps[0].title()
                    if len(first) < 5:
                        return results
                    location = first

            # ── OCR Turkish char pre-processing ──────────────────────────────
            # Variant olarak değil, ANA arama olarak düzelt → extra Overpass çağrısı yok
            # "Kaputas Plajl" → "Kaputas Plajı" (Nominatim unaccent ile bulur)
            # "Goynuk Kanyonu" → "Göynük Kanyonu"
            restored = self._restore_ocr_turkish(location)
            if restored:
                logger.info(f"🔤 OCR restored: '{location}' → '{restored}'")
                location = restored

            # ── 1. Nominatim — önce bbox'lı ara (yanlış şehir engeli)
            # Bbox boş dönerse unbounded tekrar dene + _within_city_area ile validate et.
            # use_overpass=True olan çağrılarda (OCR/POI yolu) bu unbounded retry
            # atlanır — adım 2'deki Overpass zaten bbox içinde işletme/POI arayacak,
            # ekstra bir throttled Nominatim çağrısı harcamaya değmez. NER yolunda
            # (use_overpass=False, Overpass hiç denenmez) unbounded retry tek fallback
            # olduğu için korunur.
            place_data = self.search_place(location, city_bbox=city_bbox, city_hint=city_hint, country_code=country_code)
            if not place_data and city_bbox and not use_overpass:
                place_data = self.search_place(location, city_bbox=None, city_hint=city_hint, country_code=country_code)
                if place_data and not self._within_city_area(place_data, city_center):
                    logger.info(f"🚫 Unbounded fallback yanlış şehir, atlandı: '{location}'")
                    place_data = None

            if place_data:
                osm_class  = place_data.get("class", "")
                osm_type   = place_data.get("type", "")
                importance = place_data.get("importance", 0)

                tourism_classes = {"tourism", "amenity", "historic", "leisure", "natural", "waterway"}
                is_poi     = osm_class in tourism_classes
                is_major   = osm_class == "place" and osm_type in {"city", "town", "suburb", "borough"}
                is_quarter = osm_class == "place" and osm_type in {"neighbourhood", "quarter", "district"}
                is_minor   = osm_class == "place" and osm_type in {"village", "hamlet", "locality"}

                if is_poi:        min_imp = 0.03
                elif is_major:    min_imp = 0.10
                elif is_quarter:  min_imp = 0.05   # Kaleiçi, tarihi mahalleler
                elif is_minor:    min_imp = 0.20
                else:             min_imp = 0.12

                if importance >= min_imp:
                    # City bbox varsa ve çok uzaksa → reddet (yanlış şehir eşleşmesi)
                    if not self._within_city_area(place_data, city_center):
                        logger.info(f"❌ Yanlış şehir eşleşmesi atlandı: '{location}'")
                    else:
                        place_data["category"] = self._categorize(osm_class, osm_type)
                        results.append({"original_name": location, "place_data": place_data})
                    return results

            # ── 2. Overpass fallback (işletme + plaj + şelale vb.) ──
            # Turkey-wide fallback KALDIRILDI: "Halk Plajı" → Marmaris gibi yanlış şehir bulunuyordu.
            # city_bbox varsa sadece orada ara; yoksa Türkiye genelinde.
            if use_overpass:
                bbox = city_bbox if city_bbox else TURKEY_BBOX
                ovp = self.search_poi_overpass(location, bbox=bbox)
                if ovp and self._within_city_area(ovp, city_center):
                    results.append({"original_name": location, "place_data": ovp})
                    return results

            # ── 3. OCR hata varyantları (generic — hardcode değil) ──────────
            # Kısa varyantlar (tek kelime) → sadece Overpass'ta ara, Nominatim'de değil
            # (Nominatim tek kelimeyle yanlış şehir bulur: "Mağara" → Adana)
            if use_overpass:
                for variant in self._ocr_fallback_variants(location):
                    original_words = len(location.split())
                    variant_words  = len(variant.split())

                    vdata = None
                    # Varyant orijinalden çok daha kısaysa (tek kelimeye düştüyse)
                    # sadece Overpass'ı dene — Nominatim yanlış şehir bulur
                    bbox = city_bbox if city_bbox else TURKEY_BBOX
                    if variant_words < original_words and variant_words == 1:
                        # Tek kelimeye düşen varyant → sadece Overpass bbox içinde
                        vdata = self.search_poi_overpass(variant, bbox=bbox)
                    else:
                        vdata = self.search_place(variant, city_bbox=city_bbox if use_overpass else None, city_hint=city_hint, country_code=country_code)
                        if not vdata:
                            vdata = self.search_poi_overpass(variant, bbox=bbox)

                    if vdata and self._within_city_area(vdata, city_center):
                        logger.info(f"🔧 OCR varyant düzeltmesi: '{location}' → '{variant}'")
                        vdata["original_ocr"] = location
                        results.append({"original_name": variant, "place_data": vdata})
                        break

            # ── 4. Şehir adıyla nitelendirilerek Nominatim tekrar ara ─────────
            # "Nohut Durumu" bulunamadı → "Nohut Durumu Gaziantep" dene
            # city_hint: NER ile bulunan dominant şehir adı (örn. "Gaziantep")
            if city_hint and len(location.split()) >= 2:
                city_qualified = f"{location} {city_hint}"
                cq_data = self.search_place(city_qualified, city_bbox=None, city_hint=city_hint, country_code=country_code)
                if cq_data and self._within_city_area(cq_data, city_center):
                    logger.info(f"🏙️ Şehir qualifier ile bulundu: '{city_qualified}'")
                    cq_data["category"] = self._categorize(
                        cq_data.get("class", ""), cq_data.get("type", "")
                    )
                    results.append({"original_name": location, "place_data": cq_data})

            return results

        enriched = []
        max_workers = min(4, len(locations)) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for location_results in pool.map(_process_one, locations):
                enriched.extend(location_results)

        logger.info(f"Enriched {len(enriched)}/{len(locations)} locations")
        return enriched

    # ─────────────────────────────────────────────────────────────
    # Kategori etiketleme
    # ─────────────────────────────────────────────────────────────

    def _categorize(self, osm_class: str, osm_type: str) -> str:
        mapping = {
            ("tourism",  "museum"):              "Müze",
            ("tourism",  "attraction"):          "Turistik Alan",
            ("tourism",  "viewpoint"):           "Manzara Noktası",
            ("tourism",  "hotel"):               "Konaklama",
            ("tourism",  "hostel"):              "Konaklama",
            ("tourism",  "gallery"):             "Galeri",
            ("amenity",  "cafe"):                "Kafe",
            ("amenity",  "restaurant"):          "Restoran",
            ("amenity",  "bar"):                 "Bar",
            ("amenity",  "fast_food"):           "Yemek",
            ("amenity",  "place_of_worship"):    "İbadet Yeri",
            ("amenity",  "theatre"):             "Tiyatro",
            ("amenity",  "cinema"):              "Sinema",
            ("historic", "castle"):              "Kale",
            ("historic", "ruins"):               "Tarihi Alan",
            ("historic", "mosque"):              "Cami",
            ("historic", "archaeological_site"): "Arkeolojik Alan",
            ("historic", "monument"):            "Anıt",
            ("historic", "memorial"):            "Anıt",
            ("leisure",  "park"):                "Park",
            ("leisure",  "nature_reserve"):      "Doğa Alanı",
            ("natural",  "peak"):                "Zirve",
            ("natural",  "beach"):               "Plaj",
            ("waterway", "waterfall"):           "Şelale",
            ("man_made", "bridge"):              "Köprü",
            ("place",    "city"):                "Şehir",
            ("place",    "town"):                "İlçe",
            ("place",    "village"):             "Köy",
            # İşletme türleri (Overpass'tan)
            ("amenity",  "bakery"):              "Fırın",
            ("amenity",  "ice_cream"):           "Tatlı",
            ("amenity",  "food_court"):          "Yemek",
            ("shop",     "bakery"):              "Fırın",
            ("shop",     "confectionery"):       "Pastane",
        }
        result = mapping.get((osm_class, osm_type))
        if result:
            return result
        class_map = {
            "tourism": "Turistik Alan", "amenity": "Mekan",
            "historic": "Tarihi Alan",  "leisure": "Eğlence",
            "natural": "Doğa",          "place": "Yer",
            "shop": "İşletme",
        }
        return class_map.get(osm_class, "Mekan")
