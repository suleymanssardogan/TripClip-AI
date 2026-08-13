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

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

# M33 — `trip_sharing.py`/`auth.py`'nin AYNI, ZATEN VAR OLAN deseni (yeni bir
# rate-limit altyapısı İCAT EDİLMEDİ): her LLM çağrısı gerçek bir maliyet/
# gecikme taşır ve bu route'u ÖNCEDEN hiçbir per-route limit korumuyordu —
# yalnızca core-api'nin BLANKET, TÜM kullanıcılar arasında PAYLAŞILAN
# 200/dakika varsayılanına (bkz. docs/trip-assistant.md "Rate limiting")
# güveniliyordu.
limiter      = Limiter(key_func=get_remote_address)
router       = APIRouter(tags=["trip_assistant"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantRequest(BaseModel):
    message: str
    history: List[AssistantMessage] = []


@router.post("/trips/{trip_id}/assistant")
@limiter.limit("20/minute")
async def ask_trip_assistant(
    request: Request,
    trip_id: int,
    body: AssistantRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Trip'in gerçek durak/itinerary verisine grounded, salt-okunur soru-cevap."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        # M33 — 30s'den 60s'e çıkarıldı: Milestone 32'nin araç çağrısı döngüsü
        # tek bir istekte core-api'nin AIProvider'ı en fazla 4 kez çağırmasına
        # izin verir (bkz. TripAssistantService.MAX_TOOL_CALLS + 1); gerçek
        # doğrulamada (docs/trip-assistant.md) tek bir Ollama çağrısı bile
        # ~11-18s sürebiliyordu — 30s'lik eski değer, hiçbir yeniden deneme
        # OLMASA bile araç döngüsünün gerçekçi mutlu-yol gecikmesine karşı
        # ARTIK YETERSİZDİ. 60s hâlâ core-api'nin KENDİ iç zaman aşımlarının
        # (bkz. RAGService: 90s/çağrı, GeminiService: 30s/çağrı + backoff)
        # ALTINDA — bir provider gerçekten çok yavaşsa istemci yine de
        # temiz bir 504 GATEWAY_TIMEOUT alır (bkz. web_error_wrapper),
        # sonsuza kadar ASILI KALMAZ.
        async with internal_client(60.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/assistant",
                json=body.model_dump(),
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()
