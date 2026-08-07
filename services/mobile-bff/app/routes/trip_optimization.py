"""
Mobile BFF — AI Trip Optimizer route handler'ları.

trip_sharing.py ile birebir aynı desen: input al → core-api'nin
/internal/trips/{trip_id}/optimize + /internal/trips/{trip_id}/itineraries +
/internal/itineraries/{itinerary_id} route'larını x-user-id header'ıyla
proxy'le → hatayı mobile_error_wrapper ile iOS dostu forma çevir. Burada
hiçbir optimizasyon mantığı YOK — DTO'lar core-api'nin
OptimizeTripRequest/OptimizeTripResponse ile alan-alan eşleşir (bkz.
docs/trip-optimizer-bff.md "Request/response contracts").
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response

router       = APIRouter(tags=["trip_optimization"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class OptimizeTripRequest(BaseModel):
    selected_place_ids: List[int]
    start_date: Optional[str] = None
    duration_days: Optional[int] = None
    preferred_start_time: str = "09:00"
    preferred_end_time: str = "18:00"
    strategy: str = "greedy_distance"


@router.post("/trips/{trip_id}/optimize")
async def optimize_trip(
    trip_id: int,
    body: OptimizeTripRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Library'den seçilen mekanlardan çok-günlü bir itinerary üretir ve kaydeder."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/optimize",
                json=body.model_dump(),
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.get("/trips/{trip_id}/itineraries")
async def list_itineraries(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Bu trip için şimdiye kadar üretilmiş itinerary'lerin özeti, en yeniden eskiye."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}/itineraries",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.get("/itineraries/{itinerary_id}")
async def get_itinerary(
    itinerary_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Tek bir itinerary'nin tam detayı (günler, duraklar, uyarılar)."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/itineraries/{itinerary_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()
