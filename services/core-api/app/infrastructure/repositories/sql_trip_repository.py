"""
Infrastructure katmanı — AbstractTripRepository'nin SQLAlchemy implementasyonu.
"""
from typing import Optional, List, Dict, Any
from collections import defaultdict
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.repositories.trip_repository import AbstractTripRepository
from app.models.trip import Trip
from app.models.trip_stop import TripStop
from app.models.trip_collaborator import TripCollaborator
from app.models.trip_share import TripShare
from app.models.share_token import ShareToken
from app.models.place import Place
from app.models.place_save import PlaceSave
from app.ml.route_optimizer import RouteOptimizer


class SqlTripRepository(AbstractTripRepository):

    def __init__(self, db: Session):
        self._db = db
        self._optimizer = RouteOptimizer()

    def _owned_places(self, user_id: int, place_ids: List[int]) -> List[Place]:
        """
        Kullanıcının Library'sindeki (PlaceSave ile) Place'lerden, istenen
        id'lere karşılık gelenleri döner — verilen id sayısıyla eşleşmezse
        (kullanıcıya ait olmayan/var olmayan bir id varsa) boş liste döner.
        """
        rows = (
            self._db.query(Place)
            .join(PlaceSave, PlaceSave.place_id == Place.id)
            .filter(PlaceSave.user_id == user_id, Place.id.in_(place_ids))
            .all()
        )
        if len(rows) != len(set(place_ids)):
            return []
        by_id = {p.id: p for p in rows}
        return [by_id[pid] for pid in place_ids]

    @staticmethod
    def _as_optimizer_input(places: List[Place]) -> List[Dict[str, Any]]:
        return [
            {
                "original_name": p.name,
                "place_data": {"location": {"lat": p.lat, "lng": p.lng}},
                "_place_id": p.id,
            }
            for p in places
        ]

    def create_trip(self, user_id: int, title: str, place_ids: List[int]) -> Optional[Dict[str, Any]]:
        places = self._owned_places(user_id, place_ids)
        if not places:
            return None

        result = self._optimizer.optimize_route(self._as_optimizer_input(places))
        ordered_place_ids = [loc["_place_id"] for loc in result["route"]]

        trip = Trip(
            user_id=user_id,
            title=title,
            total_distance_km=result["total_distance_km"],
        )
        self._db.add(trip)
        self._db.flush()  # id lazım

        for position, place_id in enumerate(ordered_place_ids):
            self._db.add(TripStop(trip_id=trip.id, place_id=place_id, day_index=0, order_index=position))

        self._db.commit()
        return self.get_trip(trip.id, user_id)

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

    def _stops_with_places(self, trip_id: int) -> List[Any]:
        return (
            self._db.query(TripStop, Place)
            .join(Place, Place.id == TripStop.place_id)
            .filter(TripStop.trip_id == trip_id)
            .order_by(TripStop.day_index.asc(), TripStop.order_index.asc())
            .all()
        )

    @staticmethod
    def _stop_summary(stop: TripStop, place: Place) -> Dict[str, Any]:
        return {
            "place_id": place.id,
            "name": place.name,
            "lat": place.lat,
            "lng": place.lng,
            "city": place.city,
            "category": place.category,
            "day_index": stop.day_index,
            "order_index": stop.order_index,
        }

    def get_trip(self, trip_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        access = self.resolve_access(trip_id, user_id)
        if access is None:
            return None

        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()

        rows = self._stops_with_places(trip_id)
        days: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for stop, place in rows:
            days[stop.day_index].append(self._stop_summary(stop, place))

        return {
            "id": trip.id,
            "title": trip.title,
            "total_distance_km": trip.total_distance_km,
            "created_at": trip.created_at.isoformat() if trip.created_at else None,
            "days": [days[k] for k in sorted(days.keys())],
            "stops_count": len(rows),
            "owner_id": trip.user_id,
            "your_role": access,
            "applied_itinerary_id": trip.applied_itinerary_id,
            "itinerary_applied_at": trip.itinerary_applied_at.isoformat() if trip.itinerary_applied_at else None,
        }

    def list_trips(self, user_id: int) -> List[Dict[str, Any]]:
        owned = self._db.query(Trip).filter(Trip.user_id == user_id).all()

        collab_rows = (
            self._db.query(TripCollaborator.trip_id, TripCollaborator.role)
            .filter(TripCollaborator.user_id == user_id)
            .all()
        )
        role_by_collab_trip = {trip_id: role.value for trip_id, role in collab_rows}
        collab_trips = (
            self._db.query(Trip).filter(Trip.id.in_(role_by_collab_trip.keys())).all()
            if role_by_collab_trip else []
        )

        # Sahiplik ve collaborator kümeleri tasarım gereği ayrık olmalı (bir
        # kullanıcı kendi trip'ine collaborator olarak eklenemez — bkz.
        # SqlSharingRepository.accept_by_token), ama dict ile birleştirmek
        # ucuz bir güvenlik ağı: ileride bir hata bu varsayımı bozarsa bile
        # aynı trip iki kez listelenmez.
        by_id: Dict[int, Any] = {t.id: t for t in owned}
        for t in collab_trips:
            by_id.setdefault(t.id, t)
        trips = sorted(by_id.values(), key=lambda t: t.created_at or datetime.min, reverse=True)

        counts: Dict[int, int] = {}
        if trips:
            count_rows = (
                self._db.query(TripStop.trip_id, func.count(TripStop.id))
                .filter(TripStop.trip_id.in_([t.id for t in trips]))
                .group_by(TripStop.trip_id)
                .all()
            )
            counts = dict(count_rows)

        return [
            {
                "id": t.id,
                "title": t.title,
                "total_distance_km": t.total_distance_km,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "stops_count": counts.get(t.id, 0),
                "role": "owner" if t.user_id == user_id else role_by_collab_trip.get(t.id, "viewer"),
            }
            for t in trips
        ]

    def update_stop_order(self, trip_id: int, user_id: int, order: List[List[int]]) -> str:
        access = self.resolve_access(trip_id, user_id)
        if access is None:
            return "not_found"
        if access not in ("owner", "editor"):
            return "forbidden"

        self._db.query(TripStop).filter(TripStop.trip_id == trip_id).delete()

        for day_index, day in enumerate(order):
            for order_index, place_id in enumerate(day):
                self._db.add(TripStop(
                    trip_id=trip_id, place_id=place_id,
                    day_index=day_index, order_index=order_index,
                ))

        self._db.commit()
        return "ok"

    def delete_trip(self, trip_id: int, user_id: int) -> str:
        access = self.resolve_access(trip_id, user_id)
        if access is None:
            return "not_found"
        if access != "owner":
            return "forbidden"

        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()

        # SQLite test ortamında FK ondelete=CASCADE pragma olmadan uygulanmaz —
        # bu yüzden alt kayıtları burada elle temizliyoruz (Postgres'te de doğru),
        # FK sırasına göre: share_tokens -> trip_shares -> collaborators/stops -> trip.
        share_ids = [
            row[0] for row in
            self._db.query(TripShare.id).filter(TripShare.trip_id == trip_id).all()
        ]
        if share_ids:
            self._db.query(ShareToken).filter(ShareToken.share_id.in_(share_ids)).delete(
                synchronize_session=False
            )
        self._db.query(TripShare).filter(TripShare.trip_id == trip_id).delete()
        self._db.query(TripCollaborator).filter(TripCollaborator.trip_id == trip_id).delete()
        self._db.query(TripStop).filter(TripStop.trip_id == trip_id).delete()
        self._db.delete(trip)
        self._db.commit()
        return "ok"
