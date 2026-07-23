"""
Web BFF — Plans route handler'ları.
Transformer katmanı veri şekillendirmeyi üstlenir; route sadece proxy + transform yapar.
Tüm Core API hataları web_error_wrapper aracılığıyla Next.js dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
import httpx
from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
import os
import uuid

from app.core.error_wrapper import web_error_wrapper, raise_from_response
from app.transformers.plan_transformer import (
    to_web_card,
    to_analyze_view,
    to_editor_view,
    to_share_view,
)

router = APIRouter(prefix="/plans", tags=["plans"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.get("")
async def get_plans(
    city: str | None = Query(None),
    limit: int = Query(20, le=50),
    offset: int = Query(0),
):
    """Public feed — web kart formatında."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/public", params={
                "city": city, "limit": limit, "offset": offset
            })
        if resp.status_code == 404:
            return {"plans": [], "total": 0}
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)

    data = resp.json()
    return {
        "plans": [to_web_card(p) for p in data.get("plans", [])],
        "total": data.get("total", 0),
    }


@router.get("/stats")
async def get_stats():
    """Platform istatistikleri."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/stats")
        if resp.status_code >= 400:
            # İstatistik hatası kritik değil — sıfır döndür
            return {"total_videos": 0, "total_cities": 0, "total_users": 0, "completed_videos": 0}
    return resp.json()


@router.get("/user/{user_id}")
async def get_user_plans(user_id: int):
    """
    Kullanıcıya ait planlar — dashboard formatında.

    NOT: core-api'nin /internal/videos/user/{id} route'u kullanıcının hiç
    videosu olmasa bile normal 200 + boş liste döner ("kullanıcı yok" diye bir
    hata yolu yok) — dolayısıyla >= 400 burada HER ZAMAN gerçek bir arıza
    demektir (DB'ye erişilemedi vb.), "kullanıcının videosu yok" değil. Bu
    yüzden eskiden burada yapılan sessizce boş liste dönme, dashboard'da gerçek
    bir hatayı "henüz video yok" boş durumuyla ayırt edilemez hale getiriyordu
    — şimdi hata olduğu gibi frontend'e yansıtılıyor.
    """
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/user/{user_id}")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)

    data = resp.json()
    return {
        "plans": [to_web_card(p) for p in data.get("plans", [])],
        "total": data.get("total", 0),
    }


@router.get("/{video_id}/analyze")
async def get_plan_analyze(video_id: int):
    """Analyze sayfası — lokasyon + RAG ipuçları + rota."""
    data = await _fetch_video(video_id)
    return to_analyze_view(data)


@router.get("/{video_id}/editor")
async def get_plan_editor(video_id: int):
    """Editor sayfası — gün bazlı timeline."""
    data = await _fetch_video(video_id)
    return to_editor_view(data)


@router.get("/{video_id}/share")
async def get_plan_share(video_id: int):
    """Share sayfası — hero istatistikleri + harita."""
    data = await _fetch_video(video_id)
    return to_share_view(data)


@router.get("/{video_id}")
async def get_plan(video_id: int):
    """Ham video detayı (analyze/editor/share özel endpoint'leri yetersiz kalırsa)."""
    return await _fetch_video(video_id)


class StopOrderRequest(BaseModel):
    order: list[list[int]]


@router.patch("/{video_id}/order")
async def update_plan_order(
    video_id: int,
    body: StopOrderRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Editor'de kullanıcının belirlediği durak sırasını kalıcı olarak kaydeder — geçerli JWT zorunlu."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.patch(
                f"{CORE_API_URL}/internal/videos/{video_id}/order",
                json={"order": body.order},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return resp.json()


# ── Yardımcı ──────────────────────────────────────────────────────────────────

async def _fetch_video(video_id: int) -> dict:
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return resp.json()
