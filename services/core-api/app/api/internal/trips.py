"""
Presentation katmanı — Trip route handler'ları.
Sadece: input al → service çağır → response döndür.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.application.services.trip_service import TripService
from app.application.dto.trip_dto import (
    CreateTripRequest,
    TripStopOrderRequest,
    TripDetailResponse,
    TripListResponse,
)
from app.infrastructure.repositories.sql_trip_repository import SqlTripRepository

router = APIRouter(prefix="/internal/trips", tags=["internal"])


def get_trip_service(db: Session = Depends(get_db)) -> TripService:
    return TripService(SqlTripRepository(db))


def _require_user(x_user_id: Optional[int]) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    return x_user_id


@router.post("", response_model=TripDetailResponse)
def create_trip(
    body: CreateTripRequest,
    service: TripService = Depends(get_trip_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Library'den seçilen mekanlardan TSP ile rotalanmış yeni bir Trip oluşturur."""
    user_id = _require_user(x_user_id)
    return service.create_trip(user_id, body.title, body.place_ids)


@router.get("", response_model=TripListResponse)
def list_trips(
    service: TripService = Depends(get_trip_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    return service.list_trips(user_id)


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    return service.get_trip(trip_id, user_id)


@router.patch("/{trip_id}/order")
def update_stop_order(
    trip_id: int,
    body: TripStopOrderRequest,
    service: TripService = Depends(get_trip_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Trip Detail ekranında sürükle-bırak ile belirlenen durak sırasını kaydeder."""
    user_id = _require_user(x_user_id)
    service.update_stop_order(trip_id, user_id, body.order)
    return {"success": True}


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    service.delete_trip(trip_id, user_id)
    return {"success": True}
