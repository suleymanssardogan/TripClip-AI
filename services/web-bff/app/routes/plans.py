from fastapi import APIRouter, HTTPException, Query
import httpx
import os

router = APIRouter(prefix="/plans", tags=["plans"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


@router.get("")
async def get_plans(
    city: str | None = Query(None),
    limit: int = Query(20, le=50),
    offset: int = Query(0),
):
    """Tüm completed videoları listele (public feed)"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{CORE_API_URL}/internal/videos/public", params={
            "city": city, "limit": limit, "offset": offset
        })
    if resp.status_code == 404:
        return {"plans": [], "total": 0}
    if resp.status_code >= 500:
        raise HTTPException(500, detail="Core API error")
    return resp.json()


@router.get("/stats")
async def get_stats():
    """Platform istatistikleri"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{CORE_API_URL}/internal/videos/stats")
    if resp.status_code >= 400:
        return {"total_videos": 0, "total_cities": 0, "total_users": 0}
    return resp.json()


@router.get("/{video_id}")
async def get_plan(video_id: int):
    """Tek bir gezi planı — public"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{CORE_API_URL}/internal/videos/{video_id}")
    if resp.status_code == 404:
        raise HTTPException(404, detail="Plan bulunamadı")
    if resp.status_code >= 500:
        raise HTTPException(500, detail="Core API error")
    return resp.json()


@router.get("/user/{user_id}")
async def get_user_plans(user_id: int):
    """Kullanıcıya ait planlar"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{CORE_API_URL}/internal/videos/user/{user_id}")
    if resp.status_code >= 400:
        return {"plans": [], "total": 0}
    return resp.json()
