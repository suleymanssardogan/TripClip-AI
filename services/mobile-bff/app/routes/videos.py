"""
Mobile BFF — Video route handler'ları.
Transformer katmanı iOS'a özgü veri şekillendirmeyi üstlenir.
Tüm Core API hataları mobile_error_wrapper ile iOS dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
import httpx
import os
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response
from app.transformers.video_transformer import to_mobile_summary, to_mobile_detail

limiter      = Limiter(key_func=get_remote_address)
router       = APIRouter(prefix="/videos", tags=["videos"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(400, detail={
            "code": "INVALID_FILE_TYPE",
            "message": "Yalnızca video dosyaları yüklenebilir.",
        })

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, detail={
            "code": "FILE_TOO_LARGE",
            "message": "Video dosyası çok büyük. 100 MB altında bir video seçin.",
        })

    async with mobile_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/videos/process",
                files={"file": (file.filename, content, file.content_type)},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)

    data = resp.json()
    return {"id": data["id"], "status": data["status"], "message": "Video yüklendi, işleniyor"}


@router.get("/{video_id}/progress")
async def get_video_progress(
    video_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """İşlem ilerlemesi — stage + percent (0-100)."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}/progress")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return resp.json()


@router.get("/{video_id}")
async def get_video_detail(
    video_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Video detayı — iOS ResultsView için transformer uygulanır."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return to_mobile_detail(resp.json())


@router.get("")
async def get_user_videos(user_id: int = Depends(get_current_user_id)):
    """Kullanıcının tüm videoları — iOS HomeView kart listesi."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/user/{user_id}")
        if resp.status_code >= 400:
            # Liste boşluğu kabul edilebilir — hata yerine boş döndür
            return {"plans": [], "total": 0}

    data = resp.json()
    return {
        "plans": [to_mobile_summary(p) for p in data.get("plans", [])],
        "total": data.get("total", 0),
    }
