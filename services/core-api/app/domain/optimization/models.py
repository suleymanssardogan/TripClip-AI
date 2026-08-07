"""
Domain katmanı — Trip Optimizer'ın strateji-agnostik value object'leri.

Kasıtlı olarak SQLAlchemy'den bağımsız (düz dataclass) — bir
RouteOptimizationStrategy yalnızca bu tiplerle konuşur, ORM modelleriyle
değil. Bu, "optimizer yalnızca Place entity'leri üzerinde çalışsın; video
işleme/semantic search/place extraction'dan bağımsız kalsın" mimari
kısıtının somutlaşmış hali — strateji implementasyonları `app/models`'a
veya `app/ml`'e hiç import atmaz.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class PlaceInput:
    """Bir Place'in optimizasyon için gereken minimal, salt-okunur izdüşümü."""
    place_id: int
    name: str
    lat: float
    lng: float
    category: Optional[str] = None
    # "HH:MM-HH:MM" biçiminde günlük saat aralığı — bkz. docs/trip-optimizer.md
    # "Assumptions". None ise bilinmiyor demektir (bugün Place'te bu alan
    # hiçbir pipeline tarafından doldurulmuyor — bkz. Place.opening_hours).
    opening_hours: Optional[str] = None


@dataclass(frozen=True)
class OptimizationConstraints:
    """Kullanıcının verdiği (ya da varsayılan) zamanlama kısıtları."""
    start_date: Optional[str] = None          # ISO tarih, örn. "2026-09-01"
    duration_days: Optional[int] = None        # None ise strateji gereken gün sayısını kendi türetir
    preferred_start_time: str = "09:00"         # "HH:MM"
    preferred_end_time: str = "18:00"           # "HH:MM"


@dataclass
class OptimizedStop:
    place_id: int
    name: str
    lat: float
    lng: float
    day_index: int
    order_index: int
    arrival_time: Optional[str]                 # "HH:MM" — start_date yoksa da hesaplanır (saat-yalnız)
    departure_time: Optional[str]
    visit_duration_minutes: int
    travel_time_to_next_minutes: Optional[float] = None
    travel_distance_to_next_km: Optional[float] = None


@dataclass
class OptimizedDay:
    day_index: int
    date: Optional[str]                          # start_date verildiyse ISO tarih, aksi halde None
    stops: List[OptimizedStop] = field(default_factory=list)


@dataclass
class OptimizationResult:
    days: List[OptimizedDay]
    total_distance_km: float
    total_travel_time_minutes: float
    optimization_score: float                    # 0-100, bkz. docs "Optimization score"
    warnings: List[str] = field(default_factory=list)
