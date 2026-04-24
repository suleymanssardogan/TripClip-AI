"""
Web BFF — Plan Data Transformer.

Next.js uygulamasının ihtiyaç duyduğu veri şekline dönüştürür:
  - Editor sayfası için timeline/gün yapısı oluşturur
  - Share sayfası için hero istatistikleri hesaplar
  - Explore/dashboard için kart özetleri hazırlar
"""
from typing import Any, Dict, List, Optional
import math


# ── Public Feed / Dashboard ───────────────────────────────────────────────────

def to_web_card(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Explore ve dashboard kart bileşeni için veri şekli."""
    return {
        "id":            raw.get("id"),
        "filename":      raw.get("filename"),
        "status":        raw.get("status", "unknown"),
        "duration":      raw.get("duration"),
        "created_at":    raw.get("created_at"),
        "locationsCount": raw.get("locations_count", 0),
        "topLocation":   raw.get("top_location"),
        "ocrPreview":    raw.get("ocr_preview", []),
        "processingTime": raw.get("processing_time"),
    }


# ── Analyze / Detail ──────────────────────────────────────────────────────────

def to_analyze_view(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    /analyze/[id] sayfası için veri şekli.
    Lokasyonlar + RAG ipuçları + rota birleştirilir.
    """
    ai        = raw.get("ai_results", {})
    nominatim = ai.get("nominatim", {})
    locs      = nominatim.get("deduplicated_locations") or []
    tips      = _extract_tips(ai.get("rag", {}).get("travel_tips"))
    route     = (ai.get("route") or {}).get("optimized_route") or {}

    return {
        "id":        raw.get("id"),
        "filename":  raw.get("filename"),
        "status":    raw.get("status"),
        "duration":  raw.get("duration"),
        "locations": _web_locations(locs),
        "tips":      tips,
        "route":     route,
        "transcription": (ai.get("audio") or {}).get("transcription", {}).get("transcript"),
        "ocrPois":   ai.get("ocr_pois") or [],
        "stats": {
            "locationsCount":  len(locs),
            "detectionsCount": (ai.get("detections") or {}).get("count", 0),
            "processingTime":  ai.get("processing_time"),
        },
    }


# ── Editor ────────────────────────────────────────────────────────────────────

SLOT_TIMES = ["09:00", "10:30", "12:00", "13:30", "15:00", "16:30", "18:00", "19:30"]
LOCS_PER_DAY = 4


def to_editor_view(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    /editor/[id] sayfası için timeline yapısı.
    Lokasyonları gün/saat dilimlerine böler.
    """
    ai   = raw.get("ai_results", {})
    locs = (ai.get("nominatim") or {}).get("deduplicated_locations") or []
    tips = _extract_tips((ai.get("rag") or {}).get("travel_tips"))

    days = _build_days(locs, tips)

    return {
        "id":       raw.get("id"),
        "filename": raw.get("filename"),
        "days":     days,
        "totalLocations": len(locs),
        "aiTip":    tips[0]["tip"] if tips else "Rotanı keşfetmeye hazır mısın?",
    }


def _build_days(locs: List[Dict], tips: List[Dict]) -> List[Dict]:
    if not locs:
        return []

    days: List[Dict] = []
    day_num   = 1
    slot_idx  = 0
    events: List[Dict] = []

    for i, loc in enumerate(locs):
        place = loc.get("place_data") or {}
        coord = place.get("location") or {}

        # Bu lokasyona en yakın RAG ipucunu bul
        loc_name = loc.get("original_name", "").lower()
        matched_tip = next(
            (t["tip"] for t in tips if loc_name in t.get("location", "").lower()),
            None,
        )

        events.append({
            "time":      SLOT_TIMES[slot_idx % len(SLOT_TIMES)],
            "location":  loc.get("original_name", f"Lokasyon {i + 1}"),
            "type":      place.get("type", "place"),
            "latitude":  coord.get("lat"),
            "longitude": coord.get("lng"),
            "tip":       matched_tip,
        })
        slot_idx += 1

        # Gün dolunca yeni gün başlat
        if len(events) >= LOCS_PER_DAY and i < len(locs) - 1:
            days.append({"day": day_num, "events": events})
            events  = []
            day_num += 1
            slot_idx = 0

    if events:
        days.append({"day": day_num, "events": events})

    return days


# ── Share ─────────────────────────────────────────────────────────────────────

def to_share_view(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    /share/[id] sayfası için hero istatistikleri ve lokasyon listesi.
    Haversine ile toplam mesafe hesaplanır.
    """
    ai   = raw.get("ai_results", {})
    locs = (ai.get("nominatim") or {}).get("deduplicated_locations") or []
    tips = _extract_tips((ai.get("rag") or {}).get("travel_tips"))

    web_locs   = _web_locations(locs)
    total_dist = _total_distance_km(web_locs)

    return {
        "id":       raw.get("id"),
        "filename": raw.get("filename"),
        "duration": raw.get("duration"),
        "locations": web_locs,
        "tips":     tips,
        "stats": {
            "locationsCount": len(locs),
            "totalDistanceKm": math.ceil(total_dist) if total_dist else 0,
            "duration": raw.get("duration", 0),
        },
        "firstLocation": web_locs[0] if web_locs else None,
    }


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _web_locations(locs: List[Dict]) -> List[Dict]:
    result = []
    for loc in locs:
        place = loc.get("place_data") or {}
        coord = place.get("location") or {}
        result.append({
            "name":      loc.get("original_name", ""),
            "type":      place.get("type", "place"),
            "latitude":  coord.get("lat"),
            "longitude": coord.get("lng"),
            "importance": place.get("importance", 0.5),
        })
    return result


def _extract_tips(rag_data: Any) -> List[Dict]:
    if not rag_data:
        return []
    if isinstance(rag_data, list):
        return [{"location": t.get("location", ""), "tip": t.get("tip", "")} for t in rag_data]
    if isinstance(rag_data, dict):
        return [{"location": t.get("location", ""), "tip": t.get("tip", "")} for t in (rag_data.get("tips") or [])]
    return []


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _total_distance_km(locs: List[Dict]) -> float:
    total = 0.0
    for i in range(len(locs) - 1):
        a, b = locs[i], locs[i + 1]
        if all(x is not None for x in [a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")]):
            total += _haversine_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
    return total
