"""
Trip Optimizer DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List

from app.application.dto.trip_dto import TripStopDTO


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
    # İsteğin `start_date`'i verildiyse bu günün takvim tarihi ("YYYY-MM-DD",
    # `date.isoformat()`) — verilmediyse None (bkz. Trip Planning Date
    # milestone, docs/trip-optimizer.md "API"). Zaten hem greedy_distance hem
    # ortools stratejisinin hesapladığı `OptimizedDay.date` değeri — burada
    # yeniden HESAPLANMIYOR, yalnızca artık yanıta da YANSITILIYOR (bkz.
    # SqlOptimizationRepository.get_itinerary).
    date: Optional[str] = None
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


class ApplyItineraryResponse(BaseModel):
    """bkz. docs/trip-optimizer.md 'Apply semantics'. `stops`, TripStopDTO'yu
    aynen kullanır — TripDetailResponse'ın kendi durak şekliyle bire bir
    aynı, bu yüzden REPLACE'in gerçekten ne yazdığını doğrulamak için ek bir
    dönüşüm gerekmez."""
    trip_id: int
    itinerary_id: int
    stops: List[TripStopDTO]
    stops_count: int
    applied_at: str


class ApplyHistoryEntryResponse(BaseModel):
    """bkz. docs/trip-optimizer.md 'Apply History & Undo'. `itinerary_id`
    (ApplyItineraryResponse'un aksine) OPSİYONEL: bir undo, itinerary-kökenli
    olmayan bir duruma (ör. trip'in orijinal/manuel durak listesi) dönebilir,
    ya da kaynak itinerary sonradan silinmiş olabilir (`ondelete=SET NULL`)."""
    id: int
    itinerary_id: Optional[int]
    itinerary_created_at: Optional[str] = None
    is_undo: bool
    applied_at: str
    actor_user_id: int
    is_undoable: bool


class ApplyHistoryListResponse(BaseModel):
    entries: List[ApplyHistoryEntryResponse]


class UndoApplyResponse(BaseModel):
    """ApplyItineraryResponse ile AYNI şekil (undo, kavramsal olarak 'önceki
    anlık görüntüyü uygula'), yalnızca `itinerary_id` opsiyonel (yukarıdaki
    ApplyHistoryEntryResponse ile aynı gerekçe) ve ek olarak bu undo'nun
    KENDİ oluşturduğu yeni apply-history kaydının id'sini taşır."""
    trip_id: int
    history_id: int
    itinerary_id: Optional[int]
    stops: List[TripStopDTO]
    stops_count: int
    applied_at: str
