import requests
from typing import List, Dict, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2
import logging
import time
import json
import redis
import hashlib

logger = logging.getLogger(__name__)

# Türkiye bounding box (lat_min, lon_min, lat_max, lon_max)
TURKEY_BBOX = (35.8, 25.7, 42.1, 44.8)


class PlacesService:
    """Nominatim + Overpass API for location & POI enrichment"""

    # ─────────────────────────────────────────────────────────────
    # Turkish-aware lowercase (Python str.lower() İ→i\u0307 yapar, yanlış!)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def tr_lower(s: str) -> str:
        return s.replace("İ", "i").replace("I", "ı").lower()

    def __init__(self):
        self.nominatim_url = "https://nominatim.openstreetmap.org"
        self.overpass_url  = "https://overpass-api.de/api/interpreter"
        self.headers = {
            "User-Agent": "TripClip-AI/1.0 (educational project)"
        }
        # Overpass rate limiter — community service, max 1 req/3s
        self._last_overpass_ts: float = 0.0
        self._overpass_min_interval: float = 3.0
        try:
            self.cache = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
            self.cache.ping()
            self.cache_ttl = 60 * 60 * 24 * 7
            logger.info("✅ Redis cache connected")
        except Exception as e:
            self.cache = None
            logger.warning(f"⚠️ Redis unavailable: {e}")

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
            return json.loads(raw) if raw else None
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
                     city_bbox: Optional[Tuple] = None) -> Optional[Dict]:
        """
        Nominatim ile yer ara.
        city_bbox verilirse Nominatim'in viewbox/bounded özelliği devreye girer:
        sadece o bbox içindeki sonuçlar döner — manuel mesafe hesabına gerek kalmaz.
        """
        # Cache key: bbox bağlamını da dahil et (farklı şehir = farklı sonuç)
        bbox_suffix = f"|{city_bbox}" if city_bbox else ""
        key = self._cache_key("nom", location_name + bbox_suffix)
        cached = self._cache_get(key)
        if cached:
            logger.info(f"⚡ Nominatim cache hit: {location_name}")
            return cached

        try:
            time.sleep(1)  # rate limit
            params: dict = {
                "q": f"{location_name},{country}",
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            }
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
            if resp.status_code != 200 or not resp.json():
                return None

            place = resp.json()[0]
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
                          max_km: float = 250) -> bool:
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
            # Rate limiter: Overpass community API — min 3s arayla çağır
            elapsed = time.time() - self._last_overpass_ts
            if elapsed < self._overpass_min_interval:
                time.sleep(self._overpass_min_interval - elapsed)
            self._last_overpass_ts = time.time()

            # 429 gelirse bir kez 8s bekle ve dene
            resp = requests.post(
                self.overpass_url, data={"data": query},
                headers=self.headers, timeout=15
            )
            if resp.status_code == 429:
                logger.warning("Overpass 429 → 8s bekleniyor...")
                time.sleep(8)
                self._last_overpass_ts = time.time()
                resp = requests.post(
                    self.overpass_url, data={"data": query},
                    headers=self.headers, timeout=15
                )

            if resp.status_code != 200:
                logger.warning(f"Overpass HTTP {resp.status_code} for: {name}")
                return None

            elements = resp.json().get("elements", [])
            if not elements:
                logger.info(f"Overpass: no results for '{name}'")
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
            logger.error(f"Overpass error for '{name}': {e}")
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

    def _ocr_fallback_variants(self, name: str) -> List[str]:
        """
        OCR hatalarına karşı generic varyantlar üretir.
        Hardcode düzeltme yok — karakteristik OCR hata kalıplarına göre:
          • Sondaki yanlış karakter (Mağaral → Mağara)
          • C/G başlangıç karışıklığı (Cöynük → Göynük)
          • İlk veya son kelimeyle tek başına deneme
        """
        words = name.split()
        variants: List[str] = []

        # 1. Son karakteri at (trailing OCR artifact: "l", "i", "1")
        last = words[-1]
        if len(last) > 4:
            variants.append(" ".join(words[:-1] + [last[:-1]]))

        # 2. Sadece ilk kelime (genellikle asıl yer ismi)
        if len(words) > 1 and len(words[0]) > 3:
            variants.append(words[0])

        # 3. Sadece son kelime (bazı kompozit isimlerde)
        if len(words) > 1 and len(words[-1]) > 3:
            variants.append(words[-1])

        # 4. C↔G karışıklığı (yaygın OCR hatası — Türkçe'de sık)
        for i, word in enumerate(words):
            if not word:
                continue
            swapped = None
            if word[0] in "Cc":
                swapped = ("G" if word[0].isupper() else "g") + word[1:]
            elif word[0] in "Gg":
                swapped = ("C" if word[0].isupper() else "c") + word[1:]
            if swapped:
                v = words.copy()
                v[i] = swapped
                variants.append(" ".join(v))

        # Orijinali tekrarlama
        return [v for v in variants if v.lower() != name.lower()]

    def enrich_locations(self, locations: List[str],
                         use_overpass: bool = False,
                         city_bbox: tuple = None) -> List[Dict]:
        """
        Lokasyon listesini zenginleştir.
        use_overpass=True → Nominatim bulamazsa Overpass'ı dene.
        city_bbox verilmişse merkezi bul → uzak yerleri filtrele (yanlış şehir eşleşmesi).
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

        enriched = []

        for location in locations:
            if location.startswith("##") or len(location) < 3:
                continue
            if location.endswith(("-", "?", "'")):
                continue

            # Büyük harf → son anlamlı kelimeyi al
            if location.isupper():
                last = location.split()[-1].title()
                if len(last) < 3:
                    continue
                location = last

            # ── 1. Nominatim — önce bbox'lı ara (yanlış şehir engeli)
            # Bbox boş dönerse unbounded tekrar dene + _within_city_area ile validate et.
            place_data = self.search_place(location, city_bbox=city_bbox)
            if not place_data and city_bbox:
                place_data = self.search_place(location, city_bbox=None)
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
                        enriched.append({"original_name": location, "place_data": place_data})
                    continue

            # ── 2. Overpass fallback (işletme + plaj + şelale vb.) ──
            # Turkey-wide fallback KALDIRILDI: "Halk Plajı" → Marmaris gibi yanlış şehir bulunuyordu.
            # city_bbox varsa sadece orada ara; yoksa Türkiye genelinde.
            if use_overpass:
                bbox = city_bbox if city_bbox else TURKEY_BBOX
                ovp = self.search_poi_overpass(location, bbox=bbox)
                if ovp and self._within_city_area(ovp, city_center):
                    enriched.append({"original_name": location, "place_data": ovp})
                    continue

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
                        vdata = self.search_place(variant, city_bbox=city_bbox if use_overpass else None)
                        if not vdata:
                            vdata = self.search_poi_overpass(variant, bbox=bbox)

                    if vdata and self._within_city_area(vdata, city_center):
                        logger.info(f"🔧 OCR varyant düzeltmesi: '{location}' → '{variant}'")
                        vdata["original_ocr"] = location
                        enriched.append({"original_name": variant, "place_data": vdata})
                        break

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
