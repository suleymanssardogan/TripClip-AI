from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
import httpx
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.auth import get_current_user_id

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/videos", tags=["videos"])

CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(400, detail="File must be a video")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, detail="Video too large (max 100MB)")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file.filename, content, file.content_type)}
            response = await client.post(
                f"{CORE_API_URL}/internal/videos/process",
                files=files,
                headers={"x-user-id": str(user_id)},
            )
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(500, detail=f"CORE API Error: {str(e)}")

    data = response.json()
    return {"id": data["id"], "status": data["status"], "message": "Video uploaded successfully"}


@router.get("/{video_id}")
async def get_video_status(
    video_id: int,
    user_id: int = Depends(get_current_user_id),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
    if response.status_code == 404:
        raise HTTPException(404, detail="Video not found")
    if response.status_code >= 500:
        raise HTTPException(500, detail="Core API error")
    return response.json()
