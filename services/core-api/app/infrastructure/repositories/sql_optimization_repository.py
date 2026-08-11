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
from app.infrastructure.optimization.greedy_distance_strategy import _date_for
from app.models.trip import Trip
from app.models.trip_stop import TripStop
from app.models.trip_collaborator import TripCollaborator
from app.models.place import Place
from app.models.place_save import PlaceSave
from app.models.trip_itinerary import TripItinerary
from app.models.trip_itinerary_stop import TripItineraryStop
from app.models.trip_itinerary_apply_history import TripItineraryApplyHistory
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
        # `params` isteğin kendi kopyasıdır (bkz. TripItinerary.params doc
        # yorumu — tekrar üretilebilirlik/denetim için saklanır). `start_date`
        # her zaman orada bulunur (verilmediyse None/anahtar yok) — burada
        # OKUNUYOR (Trip Planning Date milestone'undan önce hiç okunmuyordu),
        # ama YAZILMIYOR: itinerary'nin kendi kayıtlı isteği hâlâ tek kaynak,
        # bu satır yalnızca onu yanıta yansıtıyor. `_date_for` stratejilerin
        # zaten kullandığı AYNI paylaşılan yardımcı — takvim günü aritmetiği
        # burada TEKRARLANMIYOR (bkz. greedy_distance_strategy.py).
        start_date = (itinerary.params or {}).get("start_date")
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
                {"day_index": k, "date": _date_for(start_date, k), "stops": days[k]}
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

    # ── Apply History: bkz. docs/trip-optimizer.md "Apply History & Undo" ──

    def _snapshot_trip_stops(self, trip_id: int) -> List[Dict[str, Any]]:
        """Bir apply/undo işleminden HEMEN ÖNCE TripStop'ta ne varsa, onun
        JSON-serileştirilebilir anlık görüntüsü — apply_itinerary VE
        undo_apply_history TARAFINDAN paylaşılan TEK kaynak (aynı mantığın
        iki yerde tekrarlanmasını önler)."""
        rows = (
            self._db.query(TripStop)
            .filter(TripStop.trip_id == trip_id)
            .order_by(TripStop.day_index.asc(), TripStop.order_index.asc())
            .all()
        )
        return [
            {"place_id": s.place_id, "day_index": s.day_index, "order_index": s.order_index}
            for s in rows
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

        # Apply History: bu değişiklikten HEMEN ÖNCEki durumun anlık
        # görüntüsü — TripStop SİLİNMEDEN ÖNCE alınır (bkz. docs/trip-optimizer.md
        # "Apply History & Undo → Snapshot semantics"). `previous_itinerary_id`
        # bu değer `trip.applied_itinerary_id` DEĞİŞTİRİLMEDEN önce okunuyor.
        previous_stops_snapshot = self._snapshot_trip_stops(trip.id)
        previous_itinerary_id = trip.applied_itinerary_id

        # ── Mutasyon: doğrulama tamamen bitti, buradan sonrası tek commit'e kadar geri dönüşsüz değil (rollback edilebilir) ──
        self._db.query(TripStop).filter(TripStop.trip_id == trip.id).delete()
        for stop, place in stop_rows:
            self._db.add(TripStop(
                trip_id=trip.id, place_id=place.id,
                day_index=stop.day_index, order_index=stop.order_index,
            ))
        trip.applied_itinerary_id = itinerary.id
        trip.itinerary_applied_at = now
        self._db.add(TripItineraryApplyHistory(
            trip_id=trip.id, itinerary_id=itinerary.id,
            previous_itinerary_id=previous_itinerary_id,
            previous_stops=previous_stops_snapshot,
            is_undo=False, actor_user_id=user_id, applied_at=now,
        ))
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

    # ── Delete: TripItinerary + TripItineraryStop, TripStop/Place hiç etkilenmez ──

    def delete_itinerary(self, itinerary_id: int, user_id: int) -> str:
        itinerary = self._db.query(TripItinerary).filter(TripItinerary.id == itinerary_id).first()
        if itinerary is None:
            return "not_found"

        # Anti-enumeration: get_itinerary/apply_itinerary ile AYNI ilke —
        # trip'e hiç erişimi olmayan biri için "yok" ile "yasak" ayrımı
        # sızdırılmaz.
        access = self.resolve_access(itinerary.trip_id, user_id)
        if access is None:
            return "not_found"
        if access not in ("owner", "editor"):
            return "forbidden"

        # SQLite test ortamında FK ondelete=CASCADE/SET NULL pragma
        # (`PRAGMA foreign_keys=ON`) olmadan uygulanmaz — bu yüzden alt
        # kayıtları ve Trip.applied_itinerary_id referansını burada elle
        # temizliyoruz. SqlTripRepository.delete_trip'in AYNI notu/deseni;
        # Postgres'te de doğru — DB-seviyesi FK action'lar (bkz. migration'lar)
        # zaten aynı sonucu üretir, bu yalnızca ortamdan bağımsız garanti eder.
        self._db.query(TripItineraryStop).filter(
            TripItineraryStop.itinerary_id == itinerary_id
        ).delete()

        trip = self._db.query(Trip).filter(Trip.id == itinerary.trip_id).first()
        if trip is not None and trip.applied_itinerary_id == itinerary_id:
            # Dangling FK bırakma — bu itinerary "son uygulanan" olarak
            # işaretliyse referansı temizle (bkz. Trip.applied_itinerary_id
            # doc yorumu: "itinerary ileride silinebilir bir özellik
            # kazanırsa Trip bundan etkilenmemeli, yalnızca 'son uygulanan'
            # işaretçisini kaybetmeli" — tam da bu senaryo).
            trip.applied_itinerary_id = None
            trip.itinerary_applied_at = None

        # AYNI SQLite-FK-enforcement notu: TripItineraryApplyHistory'nin
        # `itinerary_id`/`previous_itinerary_id` kolonları da bu itineraries'e
        # işaret edebilir — geçmiş kayıtların KENDİSİ asla silinmez (bkz.
        # docs/trip-optimizer.md "Apply History & Undo → Deletion semantics"),
        # yalnızca artık var olmayan itinerary'e olan referansları temizlenir.
        self._db.query(TripItineraryApplyHistory).filter(
            TripItineraryApplyHistory.itinerary_id == itinerary_id
        ).update({TripItineraryApplyHistory.itinerary_id: None}, synchronize_session=False)
        self._db.query(TripItineraryApplyHistory).filter(
            TripItineraryApplyHistory.previous_itinerary_id == itinerary_id
        ).update({TripItineraryApplyHistory.previous_itinerary_id: None}, synchronize_session=False)

        self._db.delete(itinerary)
        self._db.commit()
        return "ok"

    # ── Apply History: list + undo ──────────────────────────────────────────

    def list_apply_history(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        if self.resolve_access(trip_id, user_id) is None:
            return None

        # Tek sorgu, tek LEFT JOIN — N+1 yok (Req "Do not make the list
        # endpoint perform N+1 queries"). `TripItinerary` yalnızca hâlâ var
        # olan bir itinerary için `itinerary_created_at`'i doldurmak amacıyla
        # OUTER join edilir; itinerary silinmişse (`itinerary_id` zaten
        # ondelete=SET NULL ile NULL olmuştur) `itinerary` de `None` gelir.
        rows = (
            self._db.query(TripItineraryApplyHistory, TripItinerary)
            .outerjoin(TripItinerary, TripItinerary.id == TripItineraryApplyHistory.itinerary_id)
            .filter(TripItineraryApplyHistory.trip_id == trip_id)
            .order_by(TripItineraryApplyHistory.id.desc())
            .all()
        )
        if not rows:
            return []

        # Zaten id DESC sıralı olduğundan ilk satır en yenisi.
        latest_id = rows[0][0].id

        return [
            {
                "id": history.id,
                "itinerary_id": history.itinerary_id,
                "itinerary_created_at": itinerary.created_at.isoformat() if itinerary and itinerary.created_at else None,
                "is_undo": history.is_undo,
                "applied_at": history.applied_at.isoformat() if history.applied_at else None,
                "actor_user_id": history.actor_user_id,
                "is_undoable": history.id == latest_id,
            }
            for history, itinerary in rows
        ]

    def undo_apply_history(self, trip_id: int, history_id: int, user_id: int) -> Dict[str, Any]:
        # apply_itinerary'nin KENDİ erişim konvansiyonu (403 forbidden) —
        # delete_itinerary'nin ekstra-sıkı anti-enumeration'ı burada
        # UYGULANMADI (bkz. AbstractOptimizationRepository.undo_apply_history
        # doc yorumu).
        access = self.resolve_access(trip_id, user_id)
        if access is None:
            return {"status": "trip_not_found"}
        if access not in ("owner", "editor"):
            return {"status": "forbidden"}

        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None:
            return {"status": "trip_not_found"}

        history = (
            self._db.query(TripItineraryApplyHistory)
            .filter(
                TripItineraryApplyHistory.id == history_id,
                TripItineraryApplyHistory.trip_id == trip_id,
            )
            .first()
        )
        if history is None:
            return {"status": "history_not_found"}

        # Latest-only safety rule (KRİTİK — bkz. docs/trip-optimizer.md
        # "Apply History & Undo → Latest-only safety rule"): yalnızca bu
        # trip'in EN SON apply-history kaydı geri alınabilir. Aksi halde
        # aradan geçmiş daha yeni bir apply/undo'nun durak değişiklikleri
        # sessizce ezilirdi.
        latest = (
            self._db.query(TripItineraryApplyHistory)
            .filter(TripItineraryApplyHistory.trip_id == trip_id)
            .order_by(TripItineraryApplyHistory.id.desc())
            .first()
        )
        if latest is None or latest.id != history.id:
            return {"status": "stale"}

        # Restore edilecek anlık görüntüdeki place'lerin hâlâ var olduğunu
        # doğrula — apply_itinerary'nin kendi invalid_places kontrolüyle AYNI
        # savunma ilkesi (bkz. o metodun kendi yorumu: JOIN sonucu kontrol
        # edilir, ham FK kolonuna güvenilmez).
        snapshot = history.previous_stops or []
        snapshot_place_ids = [s["place_id"] for s in snapshot]
        places_by_id = (
            {p.id: p for p in self._db.query(Place).filter(Place.id.in_(snapshot_place_ids)).all()}
            if snapshot_place_ids else {}
        )
        if any(s["place_id"] not in places_by_id for s in snapshot):
            return {"status": "invalid_places"}

        now = datetime.utcnow()

        # Bu undo'nun KENDİ apply-history kaydı için: şu an SİLİNMEK ÜZERE
        # olan (undo edilen olayın sonucu) durumun anlık görüntüsü —
        # `_snapshot_trip_stops` apply_itinerary ile AYNI yardımcı.
        current_snapshot = self._snapshot_trip_stops(trip.id)
        current_itinerary_id = trip.applied_itinerary_id

        self._db.query(TripStop).filter(TripStop.trip_id == trip.id).delete()
        for s in snapshot:
            self._db.add(TripStop(
                trip_id=trip.id, place_id=s["place_id"],
                day_index=s["day_index"], order_index=s["order_index"],
            ))
        trip.applied_itinerary_id = history.previous_itinerary_id
        # `applied_itinerary_id`/`itinerary_applied_at` her zaman BİRLİKTE
        # anlamlı — restore edilen durum itinerary-kökenli değilse (bkz.
        # "Do not guess" gereksinimi) "en son NE ZAMAN bir itinerary
        # uygulandı" sorusunun artık bir cevabı yok, bu yüzden ikisi de None.
        trip.itinerary_applied_at = now if history.previous_itinerary_id is not None else None

        new_history = TripItineraryApplyHistory(
            trip_id=trip.id, itinerary_id=history.previous_itinerary_id,
            previous_itinerary_id=current_itinerary_id,
            previous_stops=current_snapshot,
            is_undo=True, actor_user_id=user_id, applied_at=now,
        )
        self._db.add(new_history)
        self._db.commit()
        self._db.refresh(new_history)

        restored_rows = (
            self._db.query(TripStop, Place)
            .join(Place, Place.id == TripStop.place_id)
            .filter(TripStop.trip_id == trip.id)
            .order_by(TripStop.day_index.asc(), TripStop.order_index.asc())
            .all()
        )

        # Best-effort — undo zaten commit edildi, analytics yazımı
        # başarısız olsa bile kullanıcıya hata dönmemeli (apply_itinerary'nin
        # KENDİ analytics çağrısıyla aynı yerleşim/gerekçe).
        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_ITINERARY_APPLY_UNDONE,
            trip_id=trip.id,
            platform="server",
            user_id=user_id,
            source="itinerary_apply_undo",
            kind="trip",
            metadata={
                "undone_history_id": history.id,
                "new_history_id": new_history.id,
                "restored_itinerary_id": history.previous_itinerary_id,
            },
        )

        return {
            "status": "ok",
            "trip_id": trip.id,
            "history_id": new_history.id,
            "itinerary_id": history.previous_itinerary_id,
            "stops": [
                {
                    "place_id": place.id, "name": place.name, "lat": place.lat, "lng": place.lng,
                    "city": place.city, "category": place.category,
                    "day_index": stop.day_index, "order_index": stop.order_index,
                }
                for stop, place in restored_rows
            ],
            "stops_count": len(restored_rows),
            "applied_at": now.isoformat(),
        }
