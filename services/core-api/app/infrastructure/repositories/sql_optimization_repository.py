"""
Infrastructure katmanı — AbstractOptimizationRepository'nin SQLAlchemy implementasyonu.
"""
from typing import Optional, List, Dict, Any
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.repositories.optimization_repository import AbstractOptimizationRepository
from app.domain.optimization.models import PlaceInput, OptimizationResult
from app.models.trip import Trip
from app.models.trip_stop import TripStop
from app.models.trip_collaborator import TripCollaborator
from app.models.place import Place
from app.models.place_save import PlaceSave
from app.models.trip_itinerary import TripItinerary
from app.models.trip_itinerary_stop import TripItineraryStop
from app.core.analytics_events import AnalyticsEvent
from app.application.services.analytics_service import AnalyticsService, get_analytics_service


class SqlOptimizationRepository(AbstractOptimizationRepository):

    def __init__(self, db: Session, analytics: Optional[AnalyticsService] = None):
        self._db = db
        self._analytics = analytics or get_analytics_service()

    # ── Erişim ────────────────────────────────────────────────────────────────
    # SqlTripRepository.resolve_access ile bilinçli olarak aynı sorgu şekli —
    # iki repository birbirine (ya da ortak bir üçüncü sınıfa) bağımlı
    # kılınmadı, bkz. AbstractOptimizationRepository docstring'i.

    def resolve_access(self, trip_id: int, user_id: int) -> Optional[str]:
        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None:
            return None
        if trip.user_id == user_id:
            return "owner"

        collab = (
            self._db.query(TripCollaborator)
            .filter(TripCollaborator.trip_id == trip_id, TripCollaborator.user_id == user_id)
            .first()
        )
        return collab.role.value if collab else None

    # ── Place çözümleme ──────────────────────────────────────────────────────

    def get_owned_places(self, trip_id: int, place_ids: List[int]) -> Optional[List[PlaceInput]]:
        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None:
            return None

        rows = (
            self._db.query(Place)
            .join(PlaceSave, PlaceSave.place_id == Place.id)
            .filter(PlaceSave.user_id == trip.user_id, Place.id.in_(place_ids))
            .all()
        )
        if len(rows) != len(set(place_ids)):
            return None

        by_id = {p.id: p for p in rows}
        return [
            PlaceInput(
                place_id=p.id, name=p.name, lat=p.lat, lng=p.lng,
                category=p.category, opening_hours=p.opening_hours,
            )
            for p in (by_id[pid] for pid in place_ids)
        ]

    # ── Persistence ──────────────────────────────────────────────────────────

    def save_itinerary(
        self,
        trip_id: int,
        strategy_name: str,
        params: Dict[str, Any],
        result: OptimizationResult,
    ) -> int:
        itinerary = TripItinerary(
            trip_id=trip_id,
            strategy_name=strategy_name,
            optimization_score=result.optimization_score,
            total_distance_km=result.total_distance_km,
            total_travel_time_minutes=result.total_travel_time_minutes,
            params=params,
            warnings=result.warnings,
        )
        self._db.add(itinerary)
        self._db.flush()  # id lazım

        for day in result.days:
            for stop in day.stops:
                self._db.add(TripItineraryStop(
                    itinerary_id=itinerary.id,
                    place_id=stop.place_id,
                    day_index=stop.day_index,
                    order_index=stop.order_index,
                    arrival_time=stop.arrival_time,
                    departure_time=stop.departure_time,
                    visit_duration_minutes=stop.visit_duration_minutes,
                    travel_time_to_next_minutes=stop.travel_time_to_next_minutes,
                    travel_distance_to_next_km=stop.travel_distance_to_next_km,
                ))

        self._db.commit()
        return itinerary.id

    def _stops_by_day(self, itinerary_id: int) -> Dict[int, List[Dict[str, Any]]]:
        rows = (
            self._db.query(TripItineraryStop, Place)
            .outerjoin(Place, Place.id == TripItineraryStop.place_id)
            .filter(TripItineraryStop.itinerary_id == itinerary_id)
            .order_by(TripItineraryStop.day_index.asc(), TripItineraryStop.order_index.asc())
            .all()
        )
        days: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for stop, place in rows:
            days[stop.day_index].append({
                "place_id": stop.place_id,
                # Place silinmişse (ondelete=SET NULL) isim geçmiş kayıtta
                # kaybolmasın diye en azından "Silinmiş mekan" göster.
                "name": place.name if place else "Silinmiş mekan",
                "lat": place.lat if place else None,
                "lng": place.lng if place else None,
                "day_index": stop.day_index,
                "order_index": stop.order_index,
                "arrival_time": stop.arrival_time,
                "departure_time": stop.departure_time,
                "visit_duration_minutes": stop.visit_duration_minutes,
                "travel_time_to_next_minutes": stop.travel_time_to_next_minutes,
                "travel_distance_to_next_km": stop.travel_distance_to_next_km,
            })
        return days

    def get_itinerary(self, itinerary_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        itinerary = self._db.query(TripItinerary).filter(TripItinerary.id == itinerary_id).first()
        if itinerary is None:
            return None
        if self.resolve_access(itinerary.trip_id, user_id) is None:
            return None

        days = self._stops_by_day(itinerary.id)
        return {
            "id": itinerary.id,
            "trip_id": itinerary.trip_id,
            "strategy_name": itinerary.strategy_name,
            "optimization_score": itinerary.optimization_score,
            "total_distance_km": itinerary.total_distance_km,
            "total_travel_time_minutes": itinerary.total_travel_time_minutes,
            "warnings": itinerary.warnings or [],
            "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
            "days": [
                {"day_index": k, "stops": days[k]}
                for k in sorted(days.keys())
            ],
        }

    def list_itineraries(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        if self.resolve_access(trip_id, user_id) is None:
            return None

        rows = (
            self._db.query(TripItinerary)
            .filter(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.created_at.desc())
            .all()
        )
        if not rows:
            return []

        # N+1 sorgudan kaçınmak için gün/durak sayılarını tek seferde,
        # itinerary_id'ye göre gruplanmış olarak çek — bkz. iOS Itinerary
        # History ekranının days_count/stops_count ihtiyacı.
        itinerary_ids = [it.id for it in rows]
        stops_count_by_id: Dict[int, int] = dict(
            self._db.query(TripItineraryStop.itinerary_id, func.count(TripItineraryStop.id))
            .filter(TripItineraryStop.itinerary_id.in_(itinerary_ids))
            .group_by(TripItineraryStop.itinerary_id)
            .all()
        )
        days_count_by_id: Dict[int, int] = dict(
            self._db.query(TripItineraryStop.itinerary_id, func.count(func.distinct(TripItineraryStop.day_index)))
            .filter(TripItineraryStop.itinerary_id.in_(itinerary_ids))
            .group_by(TripItineraryStop.itinerary_id)
            .all()
        )

        return [
            {
                "id": it.id,
                "trip_id": it.trip_id,
                "strategy_name": it.strategy_name,
                "optimization_score": it.optimization_score,
                "total_distance_km": it.total_distance_km,
                "total_travel_time_minutes": it.total_travel_time_minutes,
                "warnings": it.warnings or [],
                "created_at": it.created_at.isoformat() if it.created_at else None,
                "days_count": days_count_by_id.get(it.id, 0),
                "stops_count": stops_count_by_id.get(it.id, 0),
            }
            for it in rows
        ]

    # ── Apply: TripItinerary → kanonik TripStop (REPLACE) ───────────────────
    #
    # bkz. docs/trip-optimizer.md "Apply semantics" — update_stop_order ile
    # AYNI transactional "sil + yeniden ekle" deseni, kaynak yalnızca farklı
    # (client payload'ı değil, kayıtlı TripItineraryStop satırları). Tüm
    # doğrulama, HİÇBİR yazma işlemi başlamadan önce, zaten commit edilmiş
    # durum üzerinden tamamlanır — atomiklik bu sıralamadan gelir: ya tüm
    # kontroller geçer ve tek bir commit ile tüm değişiklikler yazılır, ya da
    # bir kontrol başarısız olur ve HİÇBİR satır dokunulmamış kalır.

    def apply_itinerary(self, itinerary_id: int, user_id: int) -> Dict[str, Any]:
        itinerary = self._db.query(TripItinerary).filter(TripItinerary.id == itinerary_id).first()
        if itinerary is None:
            return {"status": "not_found"}

        # Anti-enumeration: get_itinerary ile aynı ilke — itinerary'nin bağlı
        # olduğu trip'e hiç erişimi olmayan biri için "yok" ile "yasak"
        # ayrımı sızdırılmaz.
        access = self.resolve_access(itinerary.trip_id, user_id)
        if access is None:
            return {"status": "not_found"}
        if access not in ("owner", "editor"):
            return {"status": "forbidden"}

        trip = self._db.query(Trip).filter(Trip.id == itinerary.trip_id).first()
        if trip is None:
            # Pratikte olamaz (trip_itineraries.trip_id ON DELETE CASCADE ile
            # trips'e bağlı — trip silinirse itinerary de gider) ama
            # resolve_access zaten trip üzerinden çalıştığı için savunmacı.
            return {"status": "not_found"}

        stop_rows = (
            self._db.query(TripItineraryStop, Place)
            .outerjoin(Place, Place.id == TripItineraryStop.place_id)
            .filter(TripItineraryStop.itinerary_id == itinerary_id)
            .order_by(TripItineraryStop.day_index.asc(), TripItineraryStop.order_index.asc())
            .all()
        )
        if not stop_rows:
            return {"status": "empty"}

        # `place` (JOIN sonucu) kontrol edilir, `stop.place_id` (ham FK
        # kolonu) DEĞİL — ikisi teorik olarak aynı olmalı (Place silinince
        # ondelete=SET NULL ile stop.place_id de null olur) ama bu, DB'nin
        # FK enforcement'ı gerçekten açık olmasına bağlı (SQLite'ta testler
        # sırasında bu VARSAYIM tuttu, ama JOIN sonucunu kontrol etmek her
        # koşulda doğru olan tek şey: "bu Place şu an gerçekten var mı".
        # İlk sürüm stop.place_id'ye güvenmişti ve tam bu yüzden AttributeError
        # ile patladı — bu test SQLite'ta gerçek FK cascade'i tetiklemedi.
        if any(place is None for _, place in stop_rows):
            return {"status": "invalid_places"}

        place_ids = [place.id for _, place in stop_rows]
        if len(place_ids) != len(set(place_ids)):
            return {"status": "duplicate_places"}

        now = datetime.utcnow()

        # ── Mutasyon: doğrulama tamamen bitti, buradan sonrası tek commit'e kadar geri dönüşsüz değil (rollback edilebilir) ──
        self._db.query(TripStop).filter(TripStop.trip_id == trip.id).delete()
        for stop, place in stop_rows:
            self._db.add(TripStop(
                trip_id=trip.id, place_id=place.id,
                day_index=stop.day_index, order_index=stop.order_index,
            ))
        trip.applied_itinerary_id = itinerary.id
        trip.itinerary_applied_at = now
        self._db.commit()

        # Best-effort — apply zaten commit edildi, analytics yazımı başarısız
        # olsa bile kullanıcıya hata dönmemeli (AnalyticsService.track kendi
        # içinde asla fırlatmaz, bkz. o modülün docstring'i).
        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_ITINERARY_APPLIED,
            trip_id=trip.id,
            platform="server",
            user_id=user_id,
            source="itinerary_apply",
            kind="trip",
            metadata={"itinerary_id": itinerary.id, "stops_count": len(stop_rows)},
        )

        return {
            "status": "ok",
            "trip_id": trip.id,
            "itinerary_id": itinerary.id,
            "stops": [
                {
                    "place_id": place.id, "name": place.name, "lat": place.lat, "lng": place.lng,
                    "city": place.city, "category": place.category,
                    "day_index": stop.day_index, "order_index": stop.order_index,
                }
                for stop, place in stop_rows
            ],
            "stops_count": len(stop_rows),
            "applied_at": now.isoformat(),
        }
