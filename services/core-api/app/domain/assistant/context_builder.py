"""
Domain katmanı — Trip Assistant context builder.

Saf fonksiyon/dataclass'lar — DB/HTTP/LLM'e hiç DOKUNMAZ (bkz.
`app/domain/optimization`'ın AYNI ilkesi). Girdi olarak zaten var olan iki
servisin ürettiği düz dict'leri alır:

  - `AbstractTripRepository.get_trip()` — trip'in KENDİ kanonik durak listesi
    (zaman çizelgesi YOK, yalnızca gün/sıra/mekan).
  - `OptimizationService.get_itinerary()` — trip'e UYGULANMIŞ bir optimizer
    itinerary'si varsa (bkz. `trip.applied_itinerary_id`), gerçek
    arrival_time/departure_time/visit_duration_minutes/date içeren tam
    çizelge.

Bu iki kaynağı BİRLEŞTİRİP tek, LLM'e verilecek yapılandırılmış bir
`TripContext`'e indirger — "Bugün nereye gideceğim?" gibi zaman-farkında
sorular yalnızca bir itinerary UYGULANMIŞSA gerçek saatlerle
cevaplanabilir; aksi halde saat bilgisi YOK, UYDURULMAZ (bkz.
"Grounding requirement").
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class ContextStop:
    place_id: int
    name: str
    order_index: int
    city: Optional[str] = None
    category: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    # Yalnızca UYGULANMIŞ bir itinerary'den geliyorsa dolu — aksi halde
    # üçü de None (bkz. modül doc yorumu, "Grounding requirement": saat
    # UYDURULMAZ, yokluğu açıkça yoklukla temsil edilir).
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    visit_duration_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "place_id": self.place_id, "name": self.name, "order_index": self.order_index,
            "city": self.city, "category": self.category,
            "has_location": self.lat is not None and self.lng is not None,
            "arrival_time": self.arrival_time, "departure_time": self.departure_time,
            "visit_duration_minutes": self.visit_duration_minutes,
        }


@dataclass
class ContextDay:
    day_index: int
    date: Optional[str]
    stops: List[ContextStop] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_index": self.day_index, "date": self.date,
            "stops": [s.to_dict() for s in self.stops],
        }


@dataclass
class TripContext:
    trip_id: int
    title: str
    today: str  # ISO tarih (YYYY-MM-DD) — "bugün"/"yarın" akıl yürütmesinin tek zemini
    has_applied_itinerary: bool
    itinerary_applied_at: Optional[str]
    days: List[ContextDay] = field(default_factory=list)

    @property
    def total_stops(self) -> int:
        return sum(len(d.stops) for d in self.days)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id, "title": self.title, "today": self.today,
            "has_applied_itinerary": self.has_applied_itinerary,
            "itinerary_applied_at": self.itinerary_applied_at,
            "total_days": len(self.days), "total_stops": self.total_stops,
            "days": [d.to_dict() for d in self.days],
        }

    def find_stop(self, day_index: int, place_id: int) -> Optional[ContextStop]:
        """Bir referansın (day_index, place_id) gerçekten context'te var olup
        olmadığını doğrulamak için — bkz. trip_assistant_service'in
        halüsinasyon referanslarını ELEDİĞİ yer."""
        for day in self.days:
            if day.day_index != day_index:
                continue
            for stop in day.stops:
                if stop.place_id == place_id:
                    return stop
        return None


def build_trip_context(
    trip: Dict[str, Any], itinerary: Optional[Dict[str, Any]], today: date,
) -> TripContext:
    """
    `trip`: `AbstractTripRepository.get_trip()`'in döndürdüğü dict — `days`:
        `List[List[{place_id, name, lat, lng, city, category, day_index,
        order_index}]]`.
    `itinerary`: uygulanmış bir itinerary varsa `OptimizationService.get_itinerary()`
        DTO'sunun `.model_dump()`'ı (`days`: `List[{day_index, date,
        stops: [...]}]`, her durakta `arrival_time`/`departure_time`/
        `visit_duration_minutes` DAHİL) — yoksa `None`.

    Öncelik: `itinerary` verilmişse onun günleri/çizelgesi KULLANILIR (gerçek
    saatler dahil) — trip'in kendi ham `days`'i YOK SAYILMAZ ama trip'in
    stop sayısı `itinerary`'ninkiyle her zaman eşleşir (Apply, itinerary'nin
    duraklarını trip_stops'a REPLACE eder — bkz. docs/trip-optimizer.md
    "Apply semantics"), bu yüzden iki kaynak arasında GERÇEK bir çelişki
    olmaz, yalnızca `itinerary` zaman çizelgesi taşıdığı için tercih edilir.
    """
    days: List[ContextDay] = []

    if itinerary is not None:
        for day in itinerary.get("days", []):
            stops = [
                ContextStop(
                    place_id=s["place_id"], name=s["name"], order_index=s["order_index"],
                    lat=s.get("lat"), lng=s.get("lng"),
                    arrival_time=s.get("arrival_time"), departure_time=s.get("departure_time"),
                    visit_duration_minutes=s.get("visit_duration_minutes"),
                )
                for s in day.get("stops", [])
                if s.get("place_id") is not None  # silinmiş mekan — bkz. ItineraryStop.place_id nullable
            ]
            days.append(ContextDay(day_index=day["day_index"], date=day.get("date"), stops=stops))
    else:
        for raw_stops in trip.get("days", []):
            if not raw_stops:
                continue
            day_index = raw_stops[0]["day_index"]
            stops = [
                ContextStop(
                    place_id=s["place_id"], name=s["name"], order_index=s["order_index"],
                    city=s.get("city"), category=s.get("category"),
                    lat=s.get("lat"), lng=s.get("lng"),
                )
                for s in raw_stops
            ]
            days.append(ContextDay(day_index=day_index, date=None, stops=stops))

    # `itinerary` yolunda city/category taşınmıyor (ItineraryStop'ta yok) —
    # trip'in kendi ham verisinden EN AZ MALIYETLİ şekilde tamamla (yeni bir
    # sorgu YOK, zaten elde olan `trip["days"]`'ten place_id'ye göre eşle).
    if itinerary is not None:
        by_place_id = {
            s["place_id"]: s
            for raw_stops in trip.get("days", [])
            for s in raw_stops
        }
        for day in days:
            for stop in day.stops:
                original = by_place_id.get(stop.place_id)
                if original:
                    stop.city = original.get("city")
                    stop.category = original.get("category")

    return TripContext(
        trip_id=trip["id"], title=trip["title"], today=today.isoformat(),
        has_applied_itinerary=itinerary is not None,
        itinerary_applied_at=trip.get("itinerary_applied_at"),
        days=days,
    )
