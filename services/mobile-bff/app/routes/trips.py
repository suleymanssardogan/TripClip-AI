"""
Mobile BFF — Trip route handler'ları.
Transformer katmanı iOS'a özgü veri şekillendirmeyi üstlenir.
Tüm Core API hataları mobile_error_wrapper ile iOS dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response
from app.transformers.trip_transformer import to_mobile_trip_detail, to_mobile_trip_list

router       = APIRouter(prefix="/trips", tags=["trips"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class CreateTripRequest(BaseModel):
    title: str
    place_ids: list[int]


@router.post("")
async def create_trip(
    body: CreateTripRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Library'den seçilen mekanlardan TSP ile rotalanmış yeni bir Trip oluşturur."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips",
                json={"title": body.title, "place_ids": body.place_ids},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return to_mobile_trip_detail(resp.json())


@router.get("")
async def list_trips(
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return to_mobile_trip_list(resp.json())


@router.get("/{trip_id}")
async def get_trip(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return to_mobile_trip_detail(resp.json())


class TripStopOrderRequest(BaseModel):
    """Gün başına place_id listesi — videos.StopOrderRequest ile aynı semantik."""
    order: list[list[int]]


@router.patch("/{trip_id}/order")
async def update_stop_order(
    trip_id: int,
    body: TripStopOrderRequest,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.patch(
                f"{CORE_API_URL}/internal/trips/{trip_id}/order",
                json={"order": body.order},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.delete(
                f"{CORE_API_URL}/internal/trips/{trip_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}
