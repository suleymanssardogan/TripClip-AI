"""
Mobile BFF — shared-trip büyüme hunisi analytics route handler'ı.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response

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
    user_id: int = Depends(get_current_user_id),
):
    """
    Shared-trip büyüme hunisi event'ini core-api'ye iletir — `platform`
    istemciden alınmaz, burada sabitlenir (bkz. web-bff'in de aynı deseni
    kullanması: bir BFF hangi platforma hizmet ettiğini zaten biliyor,
    istemciye güvenmeye gerek yok).

    202 hemen döner; core-api'nin kendisi BackgroundTasks ile async yazar,
    bu yüzden burada da hata ekrana hiç yansımaz — iOS tarafı zaten bu
    çağrıyı sessizce fire-and-forget yapıyor.
    """
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/analytics/events",
                json={
                    "event":    body.event,
                    "trip_id":  body.trip_id,
                    "platform": "ios",
                    "source":   body.source,
                    "metadata": body.metadata,
                },
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}
