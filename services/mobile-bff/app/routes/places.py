"""
Mobile BFF — Place (kütüphane) route handler'ları.
Transformer katmanı iOS'a özgü veri şekillendirmeyi üstlenir.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
import os
import uuid

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response
from app.transformers.place_transformer import to_mobile_library

router       = APIRouter(prefix="/places", tags=["places"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.get("")
async def get_library(
    city: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    semantic: bool = False,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
):
    """
    Kullanıcının tüm videolarından birikmiş mekan kütüphanesi — iOS Library ekranı.

    `semantic=true`: "o sahildeki kafe" tarzı anlamsal arama — Qdrant
    yapılandırılmamışsa veya eşleşme yoksa core-api sessizce substring
    aramasına düşer, iOS tarafında ayrı bir hata durumu ele almaya gerek yok.
    """
    rid = str(uuid.uuid4())[:8]
    params = {"limit": limit, "offset": offset}
    if city:
        params["city"] = city
    if q:
        params["q"] = q
    if category:
        params["category"] = category
    if semantic:
        params["semantic"] = "true"

    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/places",
                params=params,
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return to_mobile_library(resp.json())
