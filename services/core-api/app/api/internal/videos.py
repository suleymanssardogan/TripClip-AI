"""
Presentation katmanı — Video route handler'ları.
Sadece: input al → service çağır → response döndür.
DB sorguları, ML pipeline, json dönüşümleri burada YOK.
"""
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.application.services.video_service import VideoService
from app.application.dto.video_dto import (
    VideoUploadResponse,
    ProgressResponse,
    PlanListResponse,
    StatsResponse,
    VideoDetailResponse,
)
from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository

logger  = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router  = APIRouter(prefix="/internal/videos", tags=["internal"])


# ── Dependency Factory ────────────────────────────────────────────────────────

def get_video_service(db: Session = Depends(get_db)) -> VideoService:
    """Her request için yeni VideoService örneği — DI ile enjekte edilir."""
    return VideoService(SqlVideoRepository(db))


# ML processor ve Redis — lazy (test ortamında yoktur)
_video_processor = None
_progress_redis  = None

def _get_processor():
    global _video_processor
    if _video_processor is None:
        from app.core.services.video_processor import VideoProcessingService
        _video_processor = VideoProcessingService()
    return _video_processor

def _get_redis():
    global _progress_redis
    if _progress_redis is None:
        try:
            from app.core.services.video_processor import _progress_redis as _pr
            _progress_redis = _pr
        except Exception:
            pass
    return _progress_redis


# ── Route Handler'lar (ince) ──────────────────────────────────────────────────

@router.post("/process", response_model=VideoUploadResponse)
@limiter.limit("10/minute")
async def process_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: VideoService = Depends(get_video_service),
    x_user_id: Optional[int] = Header(default=None),
):
    content  = await file.read()
    video_id, file_path = service.create_upload(
        filename=file.filename,
        content=content,
        user_id=x_user_id or 1,
    )
    background_tasks.add_task(_run_ml_pipeline, video_id=video_id, video_path=str(file_path))
    return service.build_upload_response(video_id, file.filename)


def _run_ml_pipeline(video_id: int, video_path: str) -> None:
    """Background: ML pipeline çalıştır, sonuçları kaydet."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    repo = SqlVideoRepository(db)
    try:
        repo.mark_processing(video_id)
        result = _get_processor().process_video(video_path, video_id)
        repo.save_results(video_id, result)
        logger.info(f"✅ Video {video_id} işlendi")
    except Exception as e:
        logger.error(f"❌ Video {video_id} başarısız: {e}")
        repo.mark_failed(video_id)
    finally:
        db.close()


@router.get("/{video_id}/progress", response_model=ProgressResponse)
async def get_video_progress(
    video_id: int,
    service: VideoService = Depends(get_video_service),
):
    return service.get_progress(video_id, redis_client=_get_redis())


@router.get("/stats", response_model=StatsResponse)
async def get_platform_stats(service: VideoService = Depends(get_video_service)):
    return service.get_stats()


@router.get("/public", response_model=PlanListResponse)
async def get_public_plans(
    city: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    service: VideoService = Depends(get_video_service),
):
    return service.get_public_feed(city=city, limit=limit, offset=offset)


@router.get("/user/{user_id}", response_model=PlanListResponse)
async def get_user_videos(
    user_id: int,
    service: VideoService = Depends(get_video_service),
):
    return service.get_user_videos(user_id)


@router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video(
    video_id: int,
    service: VideoService = Depends(get_video_service),
):
    detail = service.get_video_detail(video_id)
    # JSON serileştirme tutarlılığı için (Türkçe karakter güvencesi)
    return JSONResponse(content=json.loads(detail.model_dump_json()))
