"""
Web BFF — Trip route handler'ları.

Milestone 21 (Web AI Trip Optimizer) için eklendi — web'de o zamana kadar
Trip Builder'a dair HİÇBİR sayfa/istek yoktu (yalnızca trip sharing'in davet
kabul akışı `trip_id`'yi rastgele kullanıyordu). Optimizer'ı barındıracak
minimal bir Trip Detail deneyimi için bu iki uç yeterli — trip
OLUŞTURMA/durak düzenleme/silme BİLEREK burada YOK (bkz.
docs/ios-trip-optimizer.md "Web AI Trip Optimizer" — bunlar iOS'a özel
kalmaya devam ediyor, bu milestone yalnızca optimizer'ı web'e taşıyor,
tam bir Trip Builder web modülü değil).

`trip_optimization.py` ile AYNI desen: mobile-bff'in kendi `trip_transformer.py`'si
(iOS'a özgü camelCase) burada KULLANILMIYOR — core-api'nin ham (snake_case)
yanıtı olduğu gibi iletiliyor, `trip_optimization.py`'nin zaten yaptığı gibi.
Hiçbir iş mantığı YOK.
"""
from fastapi import APIRouter, Depends
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

router       = APIRouter(prefix="/trips", tags=["trips"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.get("")
async def list_trips(
    user_id: int = Depends(get_current_user_id),
):
    """Kullanıcının sahibi olduğu VE collaborator olduğu tüm trip'ler
    (bkz. core-api `GET /internal/trips`'in kendi `resolve_access` kapsamı)."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.get("/{trip_id}")
async def get_trip(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Trip'in başlığı + kanonik durak listesi (günlere ayrılmış) + `your_role`
    (istemcinin owner/editor'a özel kontrolleri göstermek/gizlemek için
    kullandığı UI ipucu — sunucu her isteği ayrıca doğrular)."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()
