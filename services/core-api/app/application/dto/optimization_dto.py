"""
Trip Optimizer DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List


class OptimizeTripRequest(BaseModel):
    selected_place_ids: List[int]
    start_date: Optional[str] = None            # ISO tarih, örn. "2026-09-01"
    duration_days: Optional[int] = None          # verilmezse strateji gereken gün sayısını türetir
    preferred_start_time: str = "09:00"           # "HH:MM"
    preferred_end_time: str = "18:00"             # "HH:MM"
    strategy: str = "greedy_distance"             # bkz. strategy_registry.available_strategies()


class ItineraryStopResponse(BaseModel):
    place_id: Optional[int]
    name: str
    lat: Optional[float]
    lng: Optional[float]
    day_index: int
    order_index: int
    arrival_time: Optional[str]
    departure_time: Optional[str]
    visit_duration_minutes: int
    travel_time_to_next_minutes: Optional[float]
    travel_distance_to_next_km: Optional[float]


class ItineraryDayResponse(BaseModel):
    day_index: int
    stops: List[ItineraryStopResponse]


class OptimizeTripResponse(BaseModel):
    id: int
    trip_id: int
    strategy_name: str
    optimization_score: float
    total_distance_km: float
    total_travel_time_minutes: float
    warnings: List[str]
    created_at: Optional[str]
    days: List[ItineraryDayResponse]


class ItinerarySummaryResponse(BaseModel):
    id: int
    trip_id: int
    strategy_name: str
    optimization_score: float
    total_distance_km: float
    total_travel_time_minutes: float
    warnings: List[str]
    created_at: Optional[str]
    # Liste ekranının (iOS Itinerary History) days/stops'un tamamını çekmeden
    # özet gösterebilmesi için — bkz. docs/trip-optimizer-bff.md.
    days_count: int
    stops_count: int


class ItineraryListResponse(BaseModel):
    itineraries: List[ItinerarySummaryResponse]
