"""
Place DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List


class PlaceSummary(BaseModel):
    """Kütüphane listesindeki tek bir mekan."""
    id: int
    name: str
    lat: float
    lng: float
    city: Optional[str]
    address: Optional[str]
    category: Optional[str]
    save_count: int
    saved_at: Optional[str]


class LibraryResponse(BaseModel):
    places: List[PlaceSummary]
    total: int
