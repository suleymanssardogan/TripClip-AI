"""
Mobile BFF — Trip Data Transformer.

iOS uygulamasının ihtiyaç duyduğu şekle dönüştürür — place_transformer.py ile
aynı desen: gereksiz alan yok, camelCase (Swift Codable).
"""
from typing import Any, Dict


def to_mobile_trip_detail(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":               raw.get("id"),
        "title":            raw.get("title"),
        "totalDistanceKm":  raw.get("total_distance_km"),
        "createdAt":        raw.get("created_at"),
        "stopsCount":       raw.get("stops_count", 0),
        "days":             [[_to_mobile_stop(s) for s in day] for day in raw.get("days", [])],
    }


def _to_mobile_stop(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "placeId":    raw.get("place_id"),
        "name":       raw.get("name"),
        "latitude":   raw.get("lat"),
        "longitude":  raw.get("lng"),
        "city":       raw.get("city"),
        "category":   raw.get("category"),
        "dayIndex":   raw.get("day_index", 0),
        "orderIndex": raw.get("order_index", 0),
    }


def to_mobile_trip_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":              raw.get("id"),
        "title":           raw.get("title"),
        "totalDistanceKm": raw.get("total_distance_km"),
        "createdAt":       raw.get("created_at"),
        "stopsCount":      raw.get("stops_count", 0),
    }


def to_mobile_trip_list(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {"trips": [to_mobile_trip_summary(t) for t in raw.get("trips", [])]}
