"""
Web BFF — Video route handler'ları.
Video capture iOS-only (bkz. CLAUDE.md) — web sadece görüntüleme/paylaşım yapar,
yükleme endpoint'i yoktur.
Tüm Core API hataları web_error_wrapper aracılığıyla Next.js dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Depends
from app.core.internal_client import internal_client
import os
import uuid

from app.core.auth import get_optional_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

router = APIRouter(prefix="/videos", tags=["videos"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.get("/{video_id}/progress")
async def get_video_progress(
    video_id: int,
    _: int | None = Depends(get_optional_user_id),
):
    """Video işlem ilerlemesi — public erişilebilir."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}/progress")
        if resp.status_code >= 400:
            # İlerleme alınamıyorsa varsayılan döndür (UI bloklanmasın)
            return {"stage": "processing", "percent": 10}
    return resp.json()


@router.get("/{video_id}")
async def get_video(
    video_id: int,
    _: int | None = Depends(get_optional_user_id),
):
    """Video detayı — public erişilebilir (share/[id] sayfası)."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return resp.json()
