"""
Trip DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List


class CreateTripRequest(BaseModel):
    title: str
    place_ids: List[int]


class TripStopOrderRequest(BaseModel):
    """Gün başına place_id listesi — Video.StopOrderRequest ile aynı semantik."""
    order: List[List[int]]


class TripStopDTO(BaseModel):
    place_id: int
    name: str
    lat: float
    lng: float
    city: Optional[str]
    category: Optional[str]
    day_index: int
    order_index: int


class TripDetailResponse(BaseModel):
    id: int
    title: str
    total_distance_km: Optional[float]
    created_at: Optional[str]
    days: List[List[TripStopDTO]]
    stops_count: int
    owner_id: int
    # 'owner' | 'editor' | 'viewer' — isteği yapan kullanıcının BU trip'teki
    # rolü. İstemci bunu düzenleme/silme kontrollerini göstermek/gizlemek için
    # kullanır (sunucu zaten her isteği ayrıca doğruluyor, bu yalnızca UI ipucu).
    your_role: str


class TripSummaryResponse(BaseModel):
    id: int
    title: str
    total_distance_km: Optional[float]
    created_at: Optional[str]
    stops_count: int
    role: str


class TripListResponse(BaseModel):
    trips: List[TripSummaryResponse]
