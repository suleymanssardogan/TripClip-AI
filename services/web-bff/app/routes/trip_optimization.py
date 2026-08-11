"""
Web BFF — AI Trip Optimizer route handler'ları.

Mobile BFF'deki trip_optimization.py ile birebir aynı davranış (bu
özellik için web/mobil ayrımı yok — trip_sharing.py'nin aksine, burada
web de owner/editor akışının tamamını görür, bkz. docs/trip-optimizer-bff.md
"Web BFF — neden trip_sharing'den farklı"). Hiçbir optimizasyon mantığı
YOK — yalnızca core-api'yi x-user-id header'ıyla proxy'ler.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

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
    async with web_error_wrapper(request_id=rid):
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
    async with web_error_wrapper(request_id=rid):
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
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/itineraries/{itinerary_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/itineraries/{itinerary_id}/apply")
async def apply_itinerary(
    itinerary_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Kayıtlı bir itinerary'i Trip'in kanonik TripStop listesine uygular —
    API parity için mevcut (bkz. docs/trip-optimizer-bff.md), ilk UI iOS'ta.
    Gövde gerektirmez; core-api'nin kendi endpoint'i de almıyor.
    """
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/itineraries/{itinerary_id}/apply",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.delete("/itineraries/{itinerary_id}")
async def delete_itinerary(
    itinerary_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Kayıtlı bir itinerary'i kalıcı olarak siler — API parity için mevcut
    (bkz. docs/trip-optimizer-bff.md), ilk UI iOS'ta (bkz.
    docs/ios-trip-optimizer.md "Delete Saved Itinerary"). Gövde
    gerektirmez; core-api'nin kendi endpoint'i de almıyor.
    """
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.delete(
                f"{CORE_API_URL}/internal/itineraries/{itinerary_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.get("/trips/{trip_id}/itinerary-apply-history")
async def list_apply_history(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Bu trip'in TÜM apply/undo geçmişi, en yeniden eskiye — API parity
    için mevcut, ilk UI iOS'ta (bkz. docs/trip-optimizer.md 'Apply History
    & Undo')."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}/itinerary-apply-history",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/trips/{trip_id}/itinerary-apply-history/{history_id}/undo")
async def undo_apply_history(
    trip_id: int,
    history_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """
    Belirtilen apply-history kaydının önceki TripStop anlık görüntüsünü
    geri yükler — yalnızca bu trip'in EN SON apply-history kaydıysa. API
    parity için mevcut, ilk UI iOS'ta. Gövde gerektirmez; core-api'nin
    kendi endpoint'i de almıyor.
    """
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()
