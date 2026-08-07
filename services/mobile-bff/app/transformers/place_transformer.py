"""
Mobile BFF — Place (kütüphane) Data Transformer.

iOS uygulamasının ihtiyaç duyduğu şekle dönüştürür — video_transformer.py
ile aynı desen: gereksiz alan yok, camelCase (Swift Codable).
"""
from typing import Any, Dict


def to_mobile_library(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Core API'nin kütüphane yanıtını iOS LibraryView formatına dönüştürür."""
    return {
        "places": [_to_mobile_place(p) for p in raw.get("places", [])],
        "total":  raw.get("total", 0),
    }


def _to_mobile_place(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":        raw.get("id"),
        "name":      raw.get("name"),
        "latitude":  raw.get("lat"),
        "longitude": raw.get("lng"),
        "city":      raw.get("city"),
        "address":   raw.get("address"),
        "category":  raw.get("category"),
        "saveCount": raw.get("save_count", 1),
        "savedAt":   raw.get("saved_at"),
    }
