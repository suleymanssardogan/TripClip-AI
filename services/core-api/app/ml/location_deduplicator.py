from typing import List, Dict, Optional
import logging
import math
import re
import unicodedata

logger = logging.getLogger(__name__)

# Türkçe harfleri ASCII karşılıklarına indirger. `.lower()` öncesi uygulanır çünkü
# Python "İ".lower() → "i̇" (i + birleşik nokta) üretir ve bu eşleşmeyi bozar.
_TURKISH_ASCII = str.maketrans({
    "ı": "i", "İ": "i", "I": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ç": "c", "Ç": "c",
    "ö": "o", "Ö": "o",
    "ü": "u", "Ü": "u",
})


def normalize_place_name(name: Optional[str]) -> str:
    """
    Mekan adını karşılaştırılabilir bir anahtara indirger.

    Aynı mekan pipeline'a hem Gemini'den hem Nominatim'den girdiğinde isimler
    Türkçe karakterlerde ayrışıyor ("Kaş Halk Plajı" / "Kas Halk Plajı") ve
    koordinatlar birkaç metre kaydığı için mesafe kontrolü bunları yakalayamıyor.
    Normalizasyon sonrası ikisi de "kas halk plaji" olur.
    """
    if not name:
        return ""

    text = name.translate(_TURKISH_ASCII).lower()
    # Kalan diakritikleri (â, é, î …) ayrıştırıp at.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Noktalama ve fazladan boşlukları tek boşluğa indir.
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


# Türkçe iyelik/tamlama ekleri. Sondaki kelimeye takılıyor:
#   "Mermerli Plajı" / "Mermerli Plaj"   → mermerli plaj
#   "Düden Şelalesi" / "Düden Şelale"    → duden sela… (ikisi de aynı köke iner)
# Uzun ek önce denenmeli, yoksa "si" yerine "i" soyulur.
_TR_POSSESSIVE_SUFFIXES = ("sı", "si", "su", "sü", "ı", "i", "u", "ü")

# Kökün anlamsız kalmasını önleyen alt sınırlar. "Kaş" gibi kısa adlara
# dokunmuyoruz; sondaki sesli harf orada ekin değil kökün parçası.
_STEM_MIN_WORD_LEN = 5
_STEM_MIN_ROOT_LEN = 3


def place_name_stem(name: Optional[str]) -> str:
    """
    Normalize edilmiş adın son kelimesindeki Türkçe iyelik ekini düşürür.

    `normalize_place_name` tam eşleşme için; bu ise "Plajı" ile "Plaj"ı aynı
    kovaya koymak için. Tek başına birleştirme ölçütü DEĞİL — çağıran taraf
    mesafeyle birlikte kullanıyor, çünkü kök eşleşmesi tam ad eşleşmesinden
    daha zayıf bir sinyal (bkz. deduplicate_locations).
    """
    normalized = normalize_place_name(name)
    if not normalized:
        return ""

    words = normalized.split()
    last = words[-1]
    if len(last) < _STEM_MIN_WORD_LEN:
        return normalized

    for suffix in _TR_POSSESSIVE_SUFFIXES:
        if last.endswith(suffix) and len(last) - len(suffix) >= _STEM_MIN_ROOT_LEN:
            words[-1] = last[: -len(suffix)]
            break

    return " ".join(words)


class LocationDeduplicator:
    """Deduplicate enriched locations based on coordinates and normalized names"""

    # Kök eşleşmesinin geçerli sayıldığı azami mesafe. Aynı adın iki yazımı
    # geocoder'a göre birkaç yüz metre kayabiliyor; farklı ilçelerdeki aynı
    # isimli mekanlar ise bunun çok ötesinde.
    STEM_MATCH_RADIUS_KM = 1.0

    def __init__(self, distance_threshold_km: float = 5.0):
        """
        Args:
            distance_threshold_km: Locations within this distance are considered duplicates
        """
        self.distance_threshold = distance_threshold_km
        logger.info(f"✅ LocationDeduplicator initialized (threshold: {distance_threshold_km}km)")

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        Returns distance in kilometers
        """
        # Earth radius in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    def deduplicate_locations(self, enriched_locations: List[Dict]) -> List[Dict]:
        """
        Remove duplicate locations based on normalized name or coordinate proximity
        Keeps the location with higher importance score
        """
        if not enriched_locations or len(enriched_locations) <= 1:
            return enriched_locations

        deduplicated = []
        seen_coords = []
        seen_names = set()
        seen_stems = []   # (stem, lat, lng, approx) — kök eşleşmesi mesafeyle birlikte aranıyor

        # Sort by importance (if available)
        sorted_locations = sorted(
            enriched_locations,
            key=lambda x: x.get('place_data', {}).get('importance', 0),
            reverse=True
        )

        for location in sorted_locations:
            place_data = location.get('place_data', {})
            location_coords = place_data.get('location', {})

            lat = location_coords.get('lat')
            lng = location_coords.get('lng')

            if not lat or not lng:
                logger.warning(f"Location missing coordinates: {location.get('original_name')}")
                continue

            is_duplicate = False

            # Aynı normalize isim = aynı mekan. Tek bir videonun içinde aynı adın
            # iki farklı yeri göstermesi beklenmiyor, bu yüzden mesafeye bakmadan
            # eliyoruz — koordinatlar geocoder'a göre metrelerce kayabiliyor.
            name_key = normalize_place_name(location.get('original_name'))

            if name_key and name_key in seen_names:
                logger.info(
                    f"Duplicate found: {location.get('original_name')} "
                    f"(name match: '{name_key}')"
                )
                is_duplicate = True

            # ── 2) Aynı kök + yakın konum = aynı mekan ───────────────────────
            #
            # "Mermerli Plajı" ve "Mermerli Plaj" 276 m arayla iki ayrı durak
            # olarak listeleniyordu: tam ad anahtarları iyelik eki yüzünden
            # farklı, mesafe de Gemini modundaki 1 m eşiğinin üstünde.
            #
            # Kök eşleşmesi tam ad eşleşmesinden zayıf bir sinyal, o yüzden tek
            # başına değil mesafeyle birlikte kullanılıyor. İkisi bir aradayken
            # güvenli: "Güllüoğlu Baklava" ile "Elmacı Pazarı" aynı noktada ama
            # kökleri farklı; "Kaş Halk Plajı" ile "Kaputaş Plajı" kökleri
            # farklı. Yalnızca gerçekten aynı adın iki yazımı yakalanıyor.
            stem_key = place_name_stem(location.get('original_name'))

            # Konumu "yaklaşık" olan kayıtta koordinat mekanı temsil etmiyor —
            # gazetteer ismi bulamadığı için oraya şehir merkezi konmuş. Böyle
            # bir kayıt mesafe testine sokulamaz: "Kleopatra Plajı" (yaklaşık,
            # Antalya merkezi) ile "Kleopatra Plaj" (çözülmüş, 120 km ötede)
            # aynı mekan olduğu hâlde mesafe yüzünden ayrı duraklar olarak
            # listeleniyordu. Taraflardan biri yaklaşıksa kök eşleşmesi tek
            # başına yeter; liste importance'a göre sıralı olduğu için elenen
            # her zaman yaklaşık olan olur.
            is_approx = place_data.get("precision") == "approximate"

            if not is_duplicate and stem_key:
                for seen_stem, seen_lat, seen_lng, seen_approx in seen_stems:
                    if seen_stem != stem_key:
                        continue
                    if is_approx or seen_approx:
                        logger.info(
                            f"Duplicate found: {location.get('original_name')} "
                            f"(stem match: '{stem_key}', yaklaşık konum — mesafe aranmadı)"
                        )
                        is_duplicate = True
                        break
                    distance = self.calculate_distance(lat, lng, seen_lat, seen_lng)
                    if distance < self.STEM_MATCH_RADIUS_KM:
                        logger.info(
                            f"Duplicate found: {location.get('original_name')} "
                            f"(stem match: '{stem_key}', {distance*1000:.0f}m)"
                        )
                        is_duplicate = True
                        break

            # ── 3) Mesafe — koordinatı ANLAMSIZ olan kayıtlarda UYGULANMAZ ──
            #
            # `gemini_` önekli kaynaklarda koordinat mekanı temsil etmiyor:
            #
            #   · gemini_unresolved — coğrafi veritabanı ismi bulamadı, kayda
            #     şehir merkezi konuldu ve "yaklaşık" işaretlendi. Böyle bir
            #     videoda onlarca mekan AYNI noktayı paylaşır; mesafe kontrolü
            #     hepsini tek mekana indirirdi. urfa videosunda tam bu oldu:
            #     Ciğerci Aziz Usta, Safi Künefe ve Gümrük Hanı birlikte silindi.
            #
            # Ayrıca iç içe mekanlar için mesafe hiçbir eşikte doğru cevabı
            # veremez: "Güllüoğlu Baklava" Elmacı Pazarı'nın İÇİNDE, yani aynı
            # noktada — ama gezgin için iki ayrı durak.
            #
            # Bu kayıtlarda ad ve kök eşleşmesi (1 ve 2) çalışmaya devam ediyor;
            # gerçek tekrarları onlar yakalıyor.
            #
            # Gazetteer kaynaklı kayıtlarda (Nominatim/Overpass) mesafe
            # korunuyor: orada koordinat gerçek ve ayırt edici.
            source = place_data.get("source") or ""
            trust_name_only = source.startswith("gemini_")

            if not is_duplicate and not trust_name_only:
                for seen_lat, seen_lng in seen_coords:
                    distance = self.calculate_distance(lat, lng, seen_lat, seen_lng)

                    if distance < self.distance_threshold:
                        logger.info(
                            f"Duplicate found: {location.get('original_name')} "
                            f"(distance: {distance:.2f}km from existing location)"
                        )
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduplicated.append(location)
                seen_coords.append((lat, lng))
                if name_key:
                    seen_names.add(name_key)
                if stem_key:
                    seen_stems.append((stem_key, lat, lng, is_approx))

        logger.info(f"✅ Deduplication: {len(enriched_locations)} → {len(deduplicated)} locations")
        return deduplicated
    
    def get_location_summary(self, enriched_locations: List[Dict]) -> Dict:
        """Generate summary of unique locations"""
        
        deduplicated = self.deduplicate_locations(enriched_locations)
        
        summary = {
            "total_locations": len(deduplicated),
            "locations": []
        }
        
        for loc in deduplicated:
            place_data = loc.get('place_data', {})
            coords = place_data.get('location', {})
            
            summary["locations"].append({
                "name": loc.get('original_name'),
                "full_name": place_data.get('name'),
                "coordinates": {
                    "lat": coords.get('lat'),
                    "lng": coords.get('lng')
                },
                "type": place_data.get('type'),
                "importance": place_data.get('importance')
            })
        
        return summary