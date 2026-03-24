import requests
from typing import List, Dict, Optional
import logging
import time
import json
import redis
import hashlib

logger = logging.getLogger(__name__)

class PlacesService:
    """Nominatim(OpenStreetMap) for location enrichment"""

    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.headers = {
            "User-Agent": "TripClip-AI/1.0 (educational project - github.com/suleymanssardogan/TripClip-AI)"
        }
        # Redis cache
        try:
            self.cache = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
            self.cache.ping()
            self.cache_ttl = 60 * 60 * 24 * 7  # 7 gün
            logger.info("✅ Redis cache connected")
        except Exception as e:
            self.cache = None
            logger.warning(f"⚠️ Redis unavailable, caching disabled: {e}")
        
        logger.info("Nominatim service initialized")

    def _cache_key(self, location_name: str) -> str:
        """Cache key oluştur"""
        clean = location_name.lower().strip()
        return f"nominatim:{hashlib.md5(clean.encode()).hexdigest()}"

    def search_place(self, location_name: str, country: str = "Turkey") -> Optional[Dict]:
        """Search for a place using Nominatim (with Redis cache)"""

        # Cache'e bak
        if self.cache:
            try:
                cache_key = self._cache_key(location_name)
                cached = self.cache.get(cache_key)
                if cached:
                    logger.info(f"⚡ Cache hit: {location_name}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        try:
            # Rate limit: 1 request/second
            time.sleep(1)

            params = {
                "q": f"{location_name},{country}",
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            }
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=self.headers,
                timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Nominatim error: {response.status_code}")
                return None

            results = response.json()
            if not results:
                logger.info(f"No results for: {location_name}")
                return None

            place = results[0]
            place_data = {
                "name": place.get("display_name"),
                "place_id": place.get("place_id"),
                "osm_id": place.get("osm_id"),
                "osm_type": place.get("osm_type"),
                "address": place.get("display_name"),
                "location": {
                    "lat": float(place.get("lat")),
                    "lng": float(place.get("lon"))
                },
                "type": place.get("type"),
                "class": place.get("class"),
                "importance": place.get("importance"),
                "address_details": place.get("address", {})
            }
            logger.info(f"Found: {place.get('display_name')}")

            # Cache'e yaz
            if self.cache:
                try:
                    cache_key = self._cache_key(location_name)
                    self.cache.setex(cache_key, self.cache_ttl, json.dumps(place_data))
                    logger.info(f"💾 Cached: {location_name}")
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")

            return place_data

        except requests.Timeout:
            logger.error(f"Nominatim timeout for: {location_name}")
            return None
        except Exception as e:
            logger.error(f"Nominatim search error for '{location_name}': {e}")
            return None

    def enrich_locations(self, locations: List[str]) -> List[Dict]:
        """Enrich location names with Nominatim data"""
        
        if not locations:
            logger.warning("No locations to enrich")
            return []
        
        enriched = []
        
        for location in locations:
            # Temel filtreler
            if location.startswith("##") or len(location) < 3:
                logger.info(f"Skipping invalid location: {location}")
                continue
            
            # Tamamı büyük harf olanları işle - içinde şehir ismi olabilir
            if location.isupper():
                # Büyük harfli kelimelerden anlamlı isim çıkarmaya çalış
                words = location.title()  # "GÜNDE URFA" → "Günde Urfa"
                # Sadece son kelimeyi al (genelde şehir ismi sonda olur)
                last_word = location.split()[-1].title()  # "URFA"
                if len(last_word) >= 3:
                    logger.info(f"Extracting city from uppercase: {location} → {last_word}")
                    location = last_word  # Urfa olarak devam et
                else:
                    logger.info(f"Skipping uppercase noise: {location}")
                    continue
                        
            # Özel karakter ile bitenleri atla
            if location.endswith(("-", "?", "'")):
                logger.info(f"Skipping special char location: {location}")
                continue
            
            place_data = self.search_place(location)
            
            if place_data:
                # Importance skoru düşük olanları atla (gerçek lokasyon değil)
                importance = place_data.get("importance", 0)
                if importance < 0.1:
                    logger.info(f"Skipping low importance location: {location} (score: {importance:.3f})")
                    continue
                
                enriched.append({
                    "original_name": location,
                    "place_data": place_data
                })
        
        logger.info(f" Enriched {len(enriched)}/{len(locations)} locations")
        return enriched