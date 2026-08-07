"""
Web BFF — shared-trip büyüme hunisi analytics route handler'ı.
JWT opsiyonel: `/share/[id]` sayfasını gezen, giriş yapmamış bir ziyaretçi
de event gönderebilmeli (bkz. spesifikasyonun "user_id (when available)").
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_optional_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

router       = APIRouter(prefix="/analytics", tags=["analytics"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class TrackEventRequest(BaseModel):
    event: str
    trip_id: int
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/events", status_code=202)
async def track_event(
    body: TrackEventRequest,
    user_id: int | None = Depends(get_optional_user_id),
):
    """
    Shared-trip büyüme hunisi event'ini core-api'ye iletir — `platform`
    istemciden alınmaz, burada "web" olarak sabitlenir.

    202 hemen döner; core-api BackgroundTasks ile async yazar, bu yüzden
    burada da hata web sayfasına hiç yansımaz — frontend zaten bu çağrıyı
    sessizce fire-and-forget yapıyor.
    """
    rid = str(uuid.uuid4())[:8]
    headers = {"x-user-id": str(user_id)} if user_id is not None else {}
    async with web_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/analytics/events",
                json={
                    "event":    body.event,
                    "trip_id":  body.trip_id,
                    "platform": "web",
                    "source":   body.source,
                    "metadata": body.metadata,
                },
                headers=headers,
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}
