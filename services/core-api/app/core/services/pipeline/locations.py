"""OCR place filtering and geographic validation stages."""
from __future__ import annotations
import logging
import re as _re
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from app.core.services.pipeline.runtime import ServiceResult, _safe_run
logger = logging.getLogger(__name__)

class LocationStages:
    def _enrich_ocr_pois(
        self,
        ocr_pois: List[str],
        city_bbox: Optional[tuple],
        degradation_log: List[ServiceResult],
        city_hint: Optional[str] = None,
    ) -> List[Dict]:
        """OCR POI'larını geocoding ile zenginleştir."""
        if not ocr_pois:
            return []

        geo_signals = self._geo_signal_set()

        def _has_geo_signal(text: str) -> bool:
            t_l = self._tr_lower(text)
            t_f = self._ascii_fold(t_l)
            return any(s in t_l or self._ascii_fold(s) in t_f for s in geo_signals)

        overpass_pois  = [p for p in ocr_pois if _has_geo_signal(p)]
        nominatim_pois = [p for p in ocr_pois if not _has_geo_signal(p)]

        enriched: List[Dict] = []

        if overpass_pois:
            r = _safe_run(
                "Geocoding(Overpass)",
                lambda: self.places.enrich_locations(
                    overpass_pois, use_overpass=True, city_bbox=city_bbox,
                    city_hint=city_hint,
                ),
                fallback=[],
            )
            # Overpass fail/boş döndüyse → aynı lokasyonları Nominatim'e yönlendir
            if r.data:
                enriched.extend(r.data)
                degradation_log.append(r)
            else:
                logger.info("🔄 Overpass başarısız → %d POI Nominatim'e yönlendiriliyor",
                            len(overpass_pois))
                nominatim_pois = overpass_pois + nominatim_pois  # hepsini birleştir
                degradation_log.append(r)

        if nominatim_pois:
            r = _safe_run(
                "Geocoding(Nominatim)",
                lambda: self.places.enrich_locations(
                    nominatim_pois, use_overpass=False, city_bbox=city_bbox,
                    city_hint=city_hint,
                ),
                fallback=[],
            )
            enriched.extend(r.data)
            degradation_log.append(r)

        return enriched

    @staticmethod
    def _convert_vision_landmarks(vision_landmarks: List[Dict]) -> List[Dict]:
        """Google Vision landmark'larını enriched formatına çevir."""
        result = []
        for lm in vision_landmarks:
            if lm.get("latitude") and lm.get("longitude") and lm.get("confidence", 0) > 0.5:
                result.append({
                    "original_name": lm["name"],
                    "place_data": {
                        "name":       lm["name"],
                        "location":   {"lat": lm["latitude"], "lng": lm["longitude"]},
                        "type":       "landmark",
                        "importance": lm["confidence"],
                    },
                })
        return result

    def _fix_geographic_outliers(
        self,
        locations: List[Dict],
        degradation_log: List,
    ) -> List[Dict]:
        """
        Dominant ili bul, çok uzaktaki lokasyonları aynı il bbox'ıyla yeniden sorgula.

        Algoritma:
          1. Her lokasyonun il bilgisini çek (address_details.province)
          2. En sık geçen il → dominant_province
          3. Dominant ile ait lokasyonların merkez koordinatını hesapla (centroid)
          4. Centroid'e MAX_OUTLIER_KM'den uzak olanları yeniden sorgula
          5. Yeni sonuç bulunursa değiştir, bulunamazsa orijinali koru

        Örnek:
          7× Antalya + 1× Amasya (Kaleköy) + 1× İstanbul (Kaleiçi)
          → dominant = Antalya, centroid ≈ (36.5, 30.5)
          → Kaleköy Amasya 490km uzak → Antalya'da yeniden ara → Kaleköy/Kaş ✅
          → Kaleiçi İstanbul 590km uzak → Antalya'da yeniden ara → Kaleiçi/Antalya ✅
        """
        from collections import Counter
        from math import radians, sin, cos, sqrt, atan2

        MAX_OUTLIER_KM = 180   # bu kadar uzaksa outlier say
        DOMINANT_MIN   = 2     # dominant il için minimum lokasyon sayısı

        if len(locations) < 3:
            return locations   # çok az veri → filtre anlamsız

        def _haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            return R * 2 * atan2(sqrt(a), sqrt(1-a))

        def _get_coords(loc):
            pd = loc.get("place_data") or {}
            c  = pd.get("location") or {}
            return c.get("lat"), c.get("lng")

        def _get_province(loc):
            pd   = loc.get("place_data") or {}
            addr = pd.get("address_details") or {}
            return addr.get("province") or addr.get("state")

        # Adım 1: İl sayımı
        province_counter: Counter = Counter()
        for loc in locations:
            p = _get_province(loc)
            if p:
                province_counter[p] += 1

        if not province_counter:
            return locations

        dominant_province, dominant_count = province_counter.most_common(1)[0]
        if dominant_count < DOMINANT_MIN:
            return locations   # dominant yok → filtre gerekli değil

        # Adım 2: Dominant ilin centroid'i
        dominant_locs = [
            loc for loc in locations
            if _get_province(loc) == dominant_province
        ]
        valid_coords = [
            _get_coords(loc) for loc in dominant_locs
            if all(_get_coords(loc))
        ]
        if not valid_coords:
            return locations

        centroid_lat = sum(c[0] for c in valid_coords) / len(valid_coords)
        centroid_lng = sum(c[1] for c in valid_coords) / len(valid_coords)

        # Bbox: centroid ± 2°  (~220km)
        dominant_bbox = (
            centroid_lat - 2.0, centroid_lng - 2.0,
            centroid_lat + 2.0, centroid_lng + 2.0,
        )

        logger.info(
            "🌍 Coğrafi tutarlılık: dominant=%s (%d/%d lokasyon), centroid=(%.2f, %.2f)",
            dominant_province, dominant_count, len(locations),
            centroid_lat, centroid_lng,
        )

        # Adım 3: Outlier'ları tespit et ve yeniden sorgula
        result = []
        for loc in locations:
            lat, lng = _get_coords(loc)
            if lat is None or lng is None:
                result.append(loc)
                continue

            km = _haversine(centroid_lat, centroid_lng, lat, lng)
            if km <= MAX_OUTLIER_KM:
                result.append(loc)
                continue

            # Outlier — yeniden sorgula
            name = loc.get("original_name", "")
            logger.info(
                "🔄 Outlier yeniden sorgulanıyor: '%s' (%.0fkm uzak, il=%s)",
                name, km, _get_province(loc),
            )
            new_place = self.places.search_place(
                name, city_bbox=dominant_bbox, city_hint=dominant_province
            )
            if new_place:
                new_lat = (new_place.get("location") or {}).get("lat")
                new_lng = (new_place.get("location") or {}).get("lng")
                if new_lat and new_lng:
                    new_km = _haversine(centroid_lat, centroid_lng, new_lat, new_lng)
                    if new_km <= MAX_OUTLIER_KM:
                        logger.info(
                            "  ✅ '%s' taşındı: %s → %s (%.0fkm)",
                            name, _get_province(loc),
                            (new_place.get("address_details") or {}).get("province", "?"),
                            new_km,
                        )
                        loc = {**loc, "place_data": new_place}
                    else:
                        logger.info("  ⚠️ '%s' yeni sonuç da uzak (%.0fkm) — orijinal korundu", name, new_km)
            else:
                logger.info("  ⚠️ '%s' yeniden sorgu sonuç vermedi — orijinal korundu", name)

            # Buraya düşen her kayıt şüpheli: ya bölge dışında bir eşleşmeydi ya
            # da yeniden sorguyla başka bir ile taşındı. İkisi de "gazetteer'da
            # DOĞRU kaydı bulduk" demek değil — Gaziantep videosunda "Efendioğlu"
            # bu yolla Osmaniye'deki bir eczaneye bağlanmıştı ve `exact`
            # görünüyordu. Etiket artık bunu saklamıyor.
            pd = loc.get("place_data")
            if pd is not None and not (pd.get("source") or "").startswith("gemini_"):
                loc = {**loc, "place_data": {**pd, "precision": "uncertain"}}

            result.append(loc)

        return result

    @staticmethod
    def _extract_city_bbox(ner_enriched: List[Dict]) -> Optional[tuple]:
        """İlk NER lokasyonundan şehir bounding box'ı çıkar (Overpass için)."""
        if not ner_enriched:
            return None
        loc = ner_enriched[0].get("place_data", {}).get("location")
        if not loc:
            return None
        lat, lng = loc["lat"], loc["lng"]
        return (lat - 2.0, lng - 2.0, lat + 2.0, lng + 2.0)

    @staticmethod
    def _extract_city_hint(ner_enriched: List[Dict]) -> Optional[str]:
        """
        Dominant şehir adını çıkar — OCR geocoding için qualifier.
        "Nohut Durumu" → "Nohut Durumu Gaziantep" şeklinde Nominatim'de aranır.

        Çoğunluk oyu (mode) kullanılır — sadece listedeki İLK eşleşen giriş
        kullanılırsa, tek bir yanlış/alakasız geocoding sonucu (örn. BERT-NER'in
        transkriptte hayal ettiği bir yer adı) tüm videonun city_hint'ini
        yanlış yöne çekebilir. Çoğunluk arasında birden fazla doğru lokasyon
        aynı şehri işaret ediyorsa o kazanır.
        """
        if not ner_enriched:
            return None

        from collections import Counter
        votes: Counter = Counter()
        for loc in ner_enriched:
            addr = (loc.get("place_data") or {}).get("address_details") or {}
            # Nominatim address hierarchy: city > town > province > state
            for key in ("city", "town", "province", "state"):
                if name := addr.get(key):
                    votes[name] += 1
                    break
            else:
                # Fallback: original_name eğer şehir seviyesindeyse
                place = loc.get("place_data") or {}
                if place.get("type") in ("city", "town"):
                    votes[loc.get("original_name")] += 1

        if not votes:
            return None
        return votes.most_common(1)[0][0]

    # `_detect_city_from_list` KALDIRILDI.
    #
    # Geocoding öncesi şehir ipucunu 37 Türkiye şehrinden oluşan hardcode bir
    # kümeyle tahmin ediyordu. Dünyanın herhangi bir yerinden gelen bir Reels'te
    # (Barselona, Kyoto, Tiflis) hiçbir zaman eşleşmiyor ve arama bölgesiz
    # kalıyordu. Yerine Gemini'nin döndürdüğü `region` kullanılıyor —
    # bkz. gemini_service._LOCATIONS_SCHEMA.

    # ─────────────────────────────────────────────────────────────────────────
    # OCR filtre pipeline (ayrı metod — test edilebilir)
    # ─────────────────────────────────────────────────────────────────────────
