"""
Web BFF — Trip Assistant route handler (M26).

trip_optimization.py ile birebir aynı desen: input al →
core-api'nin /internal/trips/{trip_id}/assistant'ını x-user-id header'ıyla
proxy'le → hatayı web_error_wrapper ile web-dostu forma çevir. Burada
hiçbir AI/prompt/context-building mantığı YOK — core-api zaten bunu
yapıyor, burası salt bir geçiş katmanı.
"""
import os
import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

router       = APIRouter(tags=["trip_assistant"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantRequest(BaseModel):
    message: str
    history: List[AssistantMessage] = []


@router.post("/trips/{trip_id}/assistant")
async def ask_trip_assistant(
    trip_id: int,
    body: AssistantRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Trip'in gerçek durak/itinerary verisine grounded, salt-okunur soru-cevap."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(30.0) as client:  # LLM çağrısı diğer proxy'lerden daha uzun sürebilir
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/assistant",
                json=body.model_dump(),
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()
