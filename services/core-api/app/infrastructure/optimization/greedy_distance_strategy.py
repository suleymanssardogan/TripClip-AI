"""
Infrastructure katmanı — v1 route optimization stratejisi: greedy nearest-
neighbor + "route-first, cluster-second" gün bölme.

Bilinçli olarak `app/ml/route_optimizer.py`'yi (Video pipeline'ın TSP
çözücüsü) YENİDEN KULLANMIYOR — mimari kısıt "optimizer'ı video işleme/
semantic search/place extraction'dan bağımsız tut" (bkz.
docs/trip-optimizer.md "Architecture") `app/ml`'e (pipeline paketi) bir
bağımlılık açmayı engelliyor. Haversine + nearest-neighbor'ın burada ~15
satır tekrarı, iki bounded context'i birbirine bağlamaktan daha ucuz bir
bedel.

Algoritma (bkz. docs/trip-optimizer.md "Algorithm" için tam açıklama):
1. Route-first: TÜM seçili mekanlar üzerinde tek bir nearest-neighbor
   rotası çıkar (gün ayrımı yapılmadan) — coğrafi olarak yakın mekanlar
   doğal olarak art arda gelir, bu da çoklu şehir senaryolarında bile
   "yakın mekanları grupla" gereksinimini basitçe karşılar.
2. Cluster-second: bu tek rotayı, preferred_start_time/end_time'dan türeyen
   günlük zaman bütçesine göre açgözlü biçimde günlere böler. Bir durak o
   günün bütçesine sığmıyorsa yeni bir gün açılır (duration_days
   verilmediyse gün sayısı böyle kendiliğinden türer).
3. Açılış saatleri (varsa) sıralı zaman ilerleyişini etkiler: varış açılıştan
   önceyse varış açılışa ertelenir (sessizce — bu "saatlere uymak"tır);
   varış kapanıştan sonraysa bir uyarı eklenir ama v1 duraklar arasında
   yeniden dağıtım YAPMAZ (bkz. Limitations — bu tam bir kısıt çözücünün
   işi, ileride bir OR-Tools stratejisinin doğal genişleme noktası).
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.domain.optimization.strategy import RouteOptimizationStrategy
from app.domain.optimization.models import (
    PlaceInput,
    OptimizationConstraints,
    OptimizedStop,
    OptimizedDay,
    OptimizationResult,
)

# ── Sabitler (bkz. docs/trip-optimizer.md "Assumptions") ────────────────────

DEFAULT_VISIT_MINUTES = 60
CATEGORY_VISIT_MINUTES = {
    "museum": 90,
    "landmark": 30,
    "restaurant": 60,
    "park": 45,
    "viewpoint": 20,
    "shopping": 45,
}
AVG_SPEED_KMH = 25.0          # şehir-içi ortalama (trafik/ışıklar dahil) — gerçek bir routing motoru yok
LONG_SEGMENT_KM_THRESHOLD = 50.0  # bu eşiği aşan ardışık durak mesafesi muhtemelen şehirler-arası bir sıçrama
FALLBACK_START = "09:00"
FALLBACK_END = "18:00"


def _parse_hhmm(raw: str) -> int:
    """'HH:MM' → gece yarısından itibaren dakika."""
    h, m = raw.split(":")
    return int(h) * 60 + int(m)


def _format_minutes(total_minutes: float) -> str:
    wrapped = int(round(total_minutes)) % (24 * 60)
    return f"{wrapped // 60:02d}:{wrapped % 60:02d}"


def _parse_opening_hours(raw: Optional[str]) -> Optional[Tuple[int, int]]:
    """'09:00-18:00' → (540, 1080). Ayrıştırılamayan/eksik değer None döner —
    'bilinmiyor' ile aynı şekilde ele alınır (bkz. modül docstring'i)."""
    if not raw:
        return None
    try:
        open_s, close_s = raw.split("-")
        return _parse_hhmm(open_s.strip()), _parse_hhmm(close_s.strip())
    except (ValueError, AttributeError):
        return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    lat1_r, lng1_r, lat2_r, lng2_r = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def _date_for(start_date: Optional[str], day_index: int) -> Optional[str]:
    if not start_date:
        return None
    try:
        base = date.fromisoformat(start_date)
        return (base + timedelta(days=day_index)).isoformat()
    except ValueError:
        return None


class GreedyDistanceStrategy(RouteOptimizationStrategy):

    @property
    def name(self) -> str:
        return "greedy_distance"

    def _nearest_neighbor_order(self, places: List[PlaceInput]) -> List[PlaceInput]:
        n = len(places)
        if n <= 1:
            return list(places)

        visited = [False] * n
        order = [0]
        visited[0] = True
        current = 0
        for _ in range(n - 1):
            best_idx, best_dist = None, float("inf")
            for j in range(n):
                if visited[j]:
                    continue
                d = haversine_km(places[current].lat, places[current].lng, places[j].lat, places[j].lng)
                if d < best_dist:
                    best_idx, best_dist = j, d
            visited[best_idx] = True
            order.append(best_idx)
            current = best_idx
        return [places[i] for i in order]

    def optimize(
        self,
        places: List[PlaceInput],
        constraints: OptimizationConstraints,
    ) -> OptimizationResult:
        if not places:
            return OptimizationResult(
                days=[], total_distance_km=0.0, total_travel_time_minutes=0.0,
                optimization_score=100.0, warnings=[],
            )

        try:
            day_start = _parse_hhmm(constraints.preferred_start_time)
            day_end = _parse_hhmm(constraints.preferred_end_time)
            if day_end <= day_start:
                raise ValueError
        except (ValueError, AttributeError):
            day_start, day_end = _parse_hhmm(FALLBACK_START), _parse_hhmm(FALLBACK_END)

        max_days = constraints.duration_days if (constraints.duration_days and constraints.duration_days >= 1) else None

        ordered = self._nearest_neighbor_order(places)
        n = len(ordered)

        days: List[OptimizedDay] = []
        warnings: List[str] = []
        missing_hours_names: List[str] = []
        overflow_warned = False

        day_index = 0
        current_time = day_start
        current_day_stops: List[OptimizedStop] = []
        total_distance = 0.0
        total_travel_minutes = 0.0

        def flush_day() -> None:
            nonlocal day_index, current_time, current_day_stops
            if current_day_stops:
                days.append(OptimizedDay(
                    day_index=day_index,
                    date=_date_for(constraints.start_date, day_index),
                    stops=current_day_stops,
                ))
                day_index += 1
            current_day_stops = []
            current_time = day_start

        i = 0
        while i < n:
            place = ordered[i]
            forced_last_day = max_days is not None and day_index >= max_days - 1
            arrival = current_time

            open_close = _parse_opening_hours(place.opening_hours)
            if open_close is None:
                if place.opening_hours is None:
                    missing_hours_names.append(place.name)
            else:
                open_m, close_m = open_close
                if arrival < open_m:
                    arrival = open_m  # açılışı bekle — sessizce, bu doğru davranış
                if arrival >= close_m:
                    warnings.append(
                        f"{place.name}: planlanan varış saati belirtilen çalışma saatleriyle çakışıyor"
                    )

            visit_minutes = CATEGORY_VISIT_MINUTES.get(place.category, DEFAULT_VISIT_MINUTES)
            departure = arrival + visit_minutes

            if current_day_stops and not forced_last_day and departure > day_end:
                flush_day()
                continue  # aynı durağı temiz bir günde yeniden dene

            if forced_last_day and departure > day_end and not overflow_warned:
                warnings.append(
                    "İstenen gün sayısına sığmayan duraklar son güne eklendi (zaman bütçesi aşıldı)."
                )
                overflow_warned = True

            stop = OptimizedStop(
                place_id=place.place_id, name=place.name, lat=place.lat, lng=place.lng,
                day_index=day_index, order_index=len(current_day_stops),
                arrival_time=_format_minutes(arrival), departure_time=_format_minutes(departure),
                visit_duration_minutes=visit_minutes,
            )
            current_day_stops.append(stop)
            current_time = departure

            if i + 1 < n:
                nxt = ordered[i + 1]
                dist = haversine_km(place.lat, place.lng, nxt.lat, nxt.lng)
                travel_minutes = (dist / AVG_SPEED_KMH) * 60
                stop.travel_distance_to_next_km = round(dist, 2)
                stop.travel_time_to_next_minutes = round(travel_minutes, 1)
                total_distance += dist
                total_travel_minutes += travel_minutes
                if dist >= LONG_SEGMENT_KM_THRESHOLD:
                    warnings.append(
                        f"{place.name} → {nxt.name}: uzun bir seyahat segmenti ({round(dist)} km)"
                    )
                current_time += travel_minutes

            i += 1

        flush_day()

        if missing_hours_names:
            warnings.append(
                f"Açılış saatleri bilinmiyor: {len(missing_hours_names)} mekan için "
                "program bu kısıt dikkate alınmadan oluşturuldu."
            )

        avg_km = (total_distance / (n - 1)) if n > 1 else 0.0
        travel_penalty = min(40.0, avg_km * 2)
        warning_penalty = min(30.0, len(warnings) * 5)
        score = round(max(0.0, 100.0 - travel_penalty - warning_penalty), 1)

        return OptimizationResult(
            days=days,
            total_distance_km=round(total_distance, 2),
            total_travel_time_minutes=round(total_travel_minutes, 1),
            optimization_score=score,
            warnings=warnings,
        )
