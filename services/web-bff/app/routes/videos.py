"""
Web BFF — Video route handler'ları.
Tüm Core API hataları web_error_wrapper aracılığıyla Next.js dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import httpx
import os
import uuid

from app.core.auth import get_current_user_id, get_optional_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

router = APIRouter(prefix="/videos", tags=["videos"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    """Video yükle — geçerli JWT zorunlu."""
    rid = str(uuid.uuid4())[:8]

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(400, detail={
            "code": "INVALID_FILE_TYPE",
            "message": "Yalnızca video dosyaları yüklenebilir (MP4, MOV, AVI).",
        })

    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(400, detail={
            "code": "FILE_TOO_LARGE",
            "message": "Dosya boyutu çok büyük. Lütfen 200 MB'tan küçük bir video seçin.",
        })

    async with web_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/videos/process",
                files={"file": (file.filename, content, file.content_type)},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)

    data = resp.json()
    return {"id": data["id"], "status": data["status"]}


@router.get("/{video_id}/progress")
async def get_video_progress(
    video_id: int,
    _: int | None = Depends(get_optional_user_id),
):
    """Video işlem ilerlemesi — public erişilebilir."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=10.0) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return resp.json()
