"""
Presentation katmanı — Trip Optimizer route handler'ları.
Sadece: input al → service çağır → response döndür.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.application.services.optimization_service import OptimizationService
from app.application.dto.optimization_dto import (
    OptimizeTripRequest,
    OptimizeTripResponse,
    ItineraryListResponse,
    ApplyItineraryResponse,
    ApplyHistoryListResponse,
    UndoApplyResponse,
)
from app.infrastructure.repositories.sql_optimization_repository import SqlOptimizationRepository

router = APIRouter(tags=["internal"])


def get_optimization_service(db: Session = Depends(get_db)) -> OptimizationService:
    return OptimizationService(SqlOptimizationRepository(db))


def _require_user(x_user_id: Optional[int]) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    return x_user_id


@router.post("/internal/trips/{trip_id}/optimize", response_model=OptimizeTripResponse)
def optimize_trip(
    trip_id: int,
    body: OptimizeTripRequest,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Library'den seçilen mekanlardan çok-günlü, zaman-pencereli bir itinerary üretir."""
    user_id = _require_user(x_user_id)
    return service.optimize_trip(trip_id, user_id, body)


@router.get("/internal/trips/{trip_id}/itineraries", response_model=ItineraryListResponse)
def list_itineraries(
    trip_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Bu trip için şimdiye kadar üretilmiş tüm itinerary'lerin özeti, en yeniden eskiye."""
    user_id = _require_user(x_user_id)
    return service.list_itineraries(trip_id, user_id)


@router.get("/internal/itineraries/{itinerary_id}", response_model=OptimizeTripResponse)
def get_itinerary(
    itinerary_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    return service.get_itinerary(itinerary_id, user_id)


@router.post("/internal/itineraries/{itinerary_id}/apply", response_model=ApplyItineraryResponse)
def apply_itinerary(
    itinerary_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Kayıtlı bir itinerary'i, Trip'in kanonik TripStop listesine uygular
    (REPLACE — bkz. docs/trip-optimizer.md "Apply semantics"). Trip Builder'ı
    ilk kez kasıtlı olarak mutasyona uğratan optimizer işlemi; TripItinerary'nin
    kendisi hiçbir zaman değişmez, aynı itinerary güvenle tekrar uygulanabilir.
    """
    user_id = _require_user(x_user_id)
    return service.apply_itinerary(itinerary_id, user_id)


@router.delete("/internal/itineraries/{itinerary_id}")
def delete_itinerary(
    itinerary_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Bir itinerary'i kalıcı olarak siler — TripStop/Place hiç etkilenmez,
    aynı trip'in başka itinerary'leri de etkilenmez (bkz.
    docs/trip-optimizer.md "Delete Saved Itinerary"). Anti-enumeration:
    var olmayan VE erişimi olmayan (owner/editor dışı) itinerary'ler için
    aynı 404 dönülür.
    """
    user_id = _require_user(x_user_id)
    service.delete_itinerary(itinerary_id, user_id)
    return {"success": True}


@router.get("/internal/trips/{trip_id}/itinerary-apply-history", response_model=ApplyHistoryListResponse)
def list_apply_history(
    trip_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Bu trip'in TÜM apply/undo geçmişi, en yeniden eskiye (bkz.
    docs/trip-optimizer.md "Apply History & Undo")."""
    user_id = _require_user(x_user_id)
    return service.list_apply_history(trip_id, user_id)


@router.post(
    "/internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo",
    response_model=UndoApplyResponse,
)
def undo_apply_history(
    trip_id: int,
    history_id: int,
    service: OptimizationService = Depends(get_optimization_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Belirtilen apply-history kaydının önceki TripStop anlık görüntüsünü
    geri yükler — yalnızca bu trip'in EN SON apply-history kaydıysa (bkz.
    docs/trip-optimizer.md "Apply History & Undo → Latest-only safety
    rule"). Kaydedilmiş itinerary'e ASLA yazmaz. POST kullanılır (DELETE
    değil) — geri alma bir EYLEMDİR, geçmiş kaydın kendisinin silinmesi
    değil.
    """
    user_id = _require_user(x_user_id)
    return service.undo_apply(trip_id, history_id, user_id)
