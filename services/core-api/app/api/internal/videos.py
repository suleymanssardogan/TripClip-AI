"""
Presentation katmanı — Video route handler'ları.
Sadece: input al → service çağır → response döndür.
DB sorguları, ML pipeline, json dönüşümleri burada YOK.
"""
from fastapi import APIRouter, UploadFile, File, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging
import os
import re

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.application.services.video_service import VideoService
# celery_app ÖNCE import edilmeli — shared_task'ların doğru app'e bağlanması için.
# Geç import (lazy) yapılırsa shared_task localhost'a bağlanmaya çalışır.
from app.core.celery_app import celery_app as _celery_app  # noqa: F401
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


# ── Redis progress client (lazy) ──────────────────────────────────────────────
def _get_redis():
    from app.core.redis import progress_redis
    return progress_redis()


# ── Route Handler'lar (ince) ──────────────────────────────────────────────────

@router.post("/process", response_model=VideoUploadResponse)
@limiter.limit("10/minute")
async def process_video(
    request: Request,
    file: UploadFile = File(...),
    service: VideoService = Depends(get_video_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Video yükle → Celery kuyruğuna gönder → anında yanıt dön.
    Gerçek işlem Celery worker tarafından arka planda yapılır.
    """
    content = await file.read()
    video_id, file_path = service.create_upload(
        filename=file.filename,
        content=content,
        user_id=x_user_id or 1,
    )

    # ── Celery task'ı kuyruğa ekle ────────────────────────────────────────────
    try:
        from app.tasks.video_tasks import process_video_task
        task = process_video_task.delay(video_id, str(file_path))
        logger.info("📤 Celery task kuyruğa eklendi | video_id=%s | task_id=%s",
                    video_id, task.id)
    except Exception as exc:
        # Redis bağlantısı yoksa (local geliştirme) BackgroundTasks fallback
        logger.warning("⚠️  Celery ulaşılamıyor, BackgroundTasks fallback: %s", exc)
        from fastapi import BackgroundTasks
        bt = BackgroundTasks()
        bt.add_task(_fallback_run_ml_pipeline, video_id=video_id, video_path=str(file_path))

    return service.build_upload_response(video_id, file.filename)


def _fallback_run_ml_pipeline(video_id: int, video_path: str) -> None:
    """
    Celery erişilemiyorsa (local geliştirme) doğrudan çalışır.
    Production'da bu kod bloğuna girilmez.
    """
    from app.core.database import SessionLocal
    from app.core.services.video_processor import VideoProcessingService
    db   = SessionLocal()
    repo = SqlVideoRepository(db)
    try:
        repo.mark_processing(video_id)
        result = VideoProcessingService().process_video(video_path, video_id)
        repo.save_results(video_id, result)
        logger.info("✅ Fallback pipeline tamamlandı | video_id=%s", video_id)
    except Exception as e:
        logger.error("❌ Fallback pipeline başarısız | video_id=%s | %s", video_id, e)
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


# ── URL Queue Endpoint (Share Extension için) ─────────────────────────────────

_SUPPORTED_URL_PATTERN = re.compile(
    r"instagram\.com/(reel|p|tv)/|instagr\.am",
    re.IGNORECASE,
)

class URLQueueRequest(BaseModel):
    url: str
    source: str = "unknown"

    @field_validator("url")
    @classmethod
    def validate_instagram_url(cls, v: str) -> str:
        if not _SUPPORTED_URL_PATTERN.search(v):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "UNSUPPORTED_URL",
                    "message": "Yalnızca Instagram Reels/Post linkleri desteklenmektedir.",
                }
            )
        return v.strip()


@router.post("/queue-url", status_code=202)
@limiter.limit("20/minute")
async def queue_url(
    request: Request,
    body: URLQueueRequest,
    service: VideoService = Depends(get_video_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Share Extension → 202 Accepted.

    URL hemen işlenmez; Celery kuyruğuna alınır.
    İstek anında yanıt döner — kullanıcı bekletilmez.

    Akış:
        POST /queue-url  { "url": "https://instagram.com/reel/..." }
          → 202 { "id": 42, "status": "queued" }
          → Celery worker: URL'i indir → ML pipeline → DB'ye kaydet
    """
    user_id = x_user_id or 1

    # DB kaydı oluştur (status = "queued", filename = URL'den türetilir)
    url_slug = body.url.rstrip("/").rsplit("/", 1)[-1][:40]  # son path segment
    filename = f"instagram_{url_slug}.mp4"

    video_id, _ = service.create_upload(
        filename=filename,
        content=b"",          # dosya henüz yok — URL'den indirilecek
        user_id=user_id,
    )

    # Celery task — URL'i indirip işleyecek
    try:
        from app.tasks.video_tasks import process_url_task
        task = process_url_task.delay(video_id, body.url, body.source)
        logger.info(
            "📎 URL kuyruğa alındı | video_id=%s | task_id=%s | url=%.60s",
            video_id, task.id, body.url,
        )
    except Exception as exc:
        logger.warning("⚠️ Celery ulaşılamıyor, URL task atlandı: %s", exc)
        # Fallback: kaydı "queued" durumunda bırak, manuel işlenebilir

    return {
        "id":      video_id,
        "status":  "queued",
        "message": "Video kuyruğa alındı, konum bulununca bildireceğiz.",
    }
