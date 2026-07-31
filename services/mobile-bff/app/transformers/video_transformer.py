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
    ai         = raw.get("ai_results") or {}       # null JSON → empty dict
    nominatim  = ai.get("nominatim") or {}
    route_data = (ai.get("route") or {}).get("optimized_route") or {}
    rag_data   = (ai.get("rag") or {}).get("travel_tips") or {}

    locations = _shape_locations(nominatim.get("deduplicated_locations") or [])
    tips      = _shape_tips(rag_data)

    # Kullanıcı durakları düzenlediyse onun sırası TSP çıktısını ezer — rota da
    # kullanıcının sırasını izlemeli, yoksa liste bir şey, çizgi başka bir şey
    # gösterir.
    stop_order = raw.get("stop_order")
    reordered  = _apply_stop_order(locations, stop_order)
    if reordered is not None:
        locations = reordered
        route     = _route_from_locations(locations)
    else:
        route = _shape_route(route_data)

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
        "transcription": ((ai.get("audio") or {}).get("transcription") or {}).get("transcript"),
        "travelTips":   tips,
        "ocrPois":      ai.get("ocr_pois") or [],
        # İstatistik
        "detectionsCount":  (ai.get("detections") or {}).get("count") or 0,
        "processingTime":   ai.get("processing_time"),
        # Geriye dönük uyumluluk: eski iOS ResultsView ai_results.nominatim.deduplicated_locations'a bakıyor
        "ai_results":   ai if ai else None,
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


def _apply_stop_order(
    locations: List[Dict],
    stop_order: Any,
) -> Optional[List[Dict]]:
    """
    Kullanıcının kaydettiği durak sırasını uygular. Düzenleme yoksa None döner
    (çağıran o zaman AI'nin varsayılan sırasını kullanır).

    `stop_order` gün başına id listesi: [[1, 3, 2], [5, 4]]. Mobil tek gün
    kullanıyor ama web çok günlü kaydedebiliyor, o yüzden düzleştiriyoruz.

    Listede olmayan bir durak kullanıcı tarafından SİLİNMİŞ sayılır — silme ve
    sıralama tek alanda taşınıyor, ayrı bir kolona ihtiyaç kalmıyor.

    `index` alanı bilerek yeniden numaralandırılmıyor: o, deduplicated_locations
    içindeki kalıcı kimlik ve istemci bir sonraki düzenlemede aynı id'leri geri
    göndermek zorunda. Ekranda gösterilen sıra numarası istemcide dizi
    pozisyonundan üretilir.
    """
    if not stop_order or not isinstance(stop_order, list):
        return None

    by_index = {loc["index"]: loc for loc in locations}
    ordered  = [
        by_index[stop_id]
        for day in stop_order if isinstance(day, list)
        for stop_id in day if stop_id in by_index
    ]

    # Bozuk/eskimiş bir sıra (ör. yeniden işlenmiş video) yüzünden kullanıcıya
    # boş bir plan göstermeyiz — böyle bir durumda varsayılana düşeriz.
    return ordered or None


def _route_from_locations(locations: List[Dict]) -> Optional[List[Dict]]:
    """Kullanıcının durak sırasını harita polyline'ına çevirir."""
    if len(locations) < 2:
        return None
    return [
        {"latitude": loc["latitude"], "longitude": loc["longitude"], "name": loc["name"]}
        for loc in locations
    ]


def _shape_route(route_data: Dict) -> Optional[List[Dict]]:
    """TSP rota sırasını koordinat listesine çevirir.

    DB'deki route yapısı:
      optimized_route.route[].original_name
      optimized_route.route[].place_data.location.lat / .lng
    """
    if not route_data:
        return None

    # video_processor.py TSP çıktısı "route" key'i kullanıyor
    ordered = route_data.get("route") or []
    result  = []
    for loc in ordered:
        place = loc.get("place_data") or {}
        coord = place.get("location") or {}
        lat   = coord.get("lat")
        lng   = coord.get("lng")
        if lat is None or lng is None:
            continue
        result.append({
            "latitude":  lat,
            "longitude": lng,
            "name":      loc.get("original_name") or place.get("name", ""),
        })
    return result or None


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
