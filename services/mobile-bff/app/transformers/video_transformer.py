"""
Mobile BFF — Video Data Transformer.

iOS uygulamasının ihtiyaç duyduğu veri şekline dönüştürür:
  - Gereksiz alanları düşürür (bant genişliği tasarrufu)
  - iOS model yapısına uygun flatten eder
  - Koordinatları MapKit formatına çevirir
"""
from typing import Any, Dict, List, Optional


def to_mobile_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core API'nin plan listesi öğesini iOS card formatına dönüştürür.
    Dashboard / history ekranında kullanılır.
    """
    return {
        "id":              raw.get("id"),
        "filename":        raw.get("filename"),
        "status":          raw.get("status", "unknown"),
        "duration":        raw.get("duration"),
        "createdAt":       raw.get("created_at"),          # camelCase — Swift Codable
        "locationsCount":  raw.get("locations_count", 0),
        "topLocation":     raw.get("top_location"),
        "processingTime":  raw.get("processing_time"),
    }


def to_mobile_detail(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core API'nin video detayını iOS ResultsView modeline dönüştürür.
    Koordinatları MapKit'in CLLocationCoordinate2D formatına getirir.
    """
    ai = raw.get("ai_results", {})
    nominatim = ai.get("nominatim", {})
    route_data = ai.get("route", {}).get("optimized_route", {})
    rag_data   = ai.get("rag", {}).get("travel_tips", {})

    locations = _shape_locations(nominatim.get("deduplicated_locations") or [])
    route      = _shape_route(route_data)
    tips       = _shape_tips(rag_data)

    return {
        "id":           raw.get("id"),
        "filename":     raw.get("filename"),
        "status":       raw.get("status"),
        "duration":     raw.get("duration"),
        "createdAt":    raw.get("created_at"),
        # Harita verisi
        "locations":    locations,
        "route":        route,
        # AI özet
        "transcription": (ai.get("audio") or {}).get("transcription", {}).get("transcript"),
        "travelTips":   tips,
        "ocrPois":      ai.get("ocr_pois") or [],
        # İstatistik
        "detectionsCount":  (ai.get("detections") or {}).get("count", 0),
        "processingTime":   ai.get("processing_time"),
    }


def _shape_locations(locs: List[Dict]) -> List[Dict]:
    """Lokasyonları MapKit annotation formatına dönüştürür."""
    result = []
    for i, loc in enumerate(locs):
        place = loc.get("place_data") or {}
        coord = place.get("location") or {}
        lat   = coord.get("lat")
        lng   = coord.get("lng")
        if lat is None or lng is None:
            continue
        result.append({
            "index":     i + 1,                          # harita pin numarası
            "name":      loc.get("original_name", ""),
            "type":      place.get("type", "place"),
            "latitude":  lat,
            "longitude": lng,
            "importance": place.get("importance", 0.5),
        })
    return result


def _shape_route(route_data: Dict) -> Optional[List[Dict]]:
    """TSP rota sırasını koordinat listesine çevirir."""
    if not route_data:
        return None
    ordered = route_data.get("ordered_locations") or []
    return [
        {
            "latitude":  loc.get("lat"),
            "longitude": loc.get("lng"),
            "name":      loc.get("name", ""),
        }
        for loc in ordered
        if loc.get("lat") and loc.get("lng")
    ]


def _shape_tips(rag_data: Any) -> List[Dict]:
    """RAG travel tips'i iOS listesi için düzleştirir."""
    if not rag_data:
        return []
    if isinstance(rag_data, list):
        return [{"location": t.get("location", ""), "tip": t.get("tip", "")} for t in rag_data]
    if isinstance(rag_data, dict):
        tips = rag_data.get("tips") or []
        return [{"location": t.get("location", ""), "tip": t.get("tip", "")} for t in tips]
    return []
