from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.models.video import Video, VideoStatus
from app.core.services.video_processor import VideoProcessingService, _progress_redis
import uuid
from pathlib import Path
import logging
from fastapi.responses import JSONResponse
import json


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/videos", tags=["internal"])

UPLOAD_DIR = Path("/app/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

video_processor = VideoProcessingService()


@router.post("/process")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Video upload + background processing
    """
    
    # 1. Save file
    video_id_str = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{video_id_str}{file_extension}"
    
    logger.info(f"Uploading video: {file.filename}")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    logger.info(f"Video saved: {file_path}")
    
    # 2. Database'e kaydet
    db_video = Video(
        filename=file.filename,
        file_path=str(file_path),
        status=VideoStatus.UPLOADED,
        user_id=x_user_id or 1
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    logger.info(f"Video DB record created: ID={db_video.id}")
    
    # 3. Background task: Video processing
    background_tasks.add_task(
        process_video_background,
        video_id=db_video.id,
        video_path=str(file_path)
    )
    
    return {
        "id": db_video.id,
        "filename": db_video.filename,
        "status": db_video.status.value,
        "message": "Video uploaded! Processing started in background."
    }


def process_video_background(video_id: int, video_path: str):
    """ Arkaplanda video işleme"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    
    try:
        logger.info(f"🎬 Starting background processing for video {video_id}")
        
        video = db.query(Video).filter(Video.id == video_id).first()
        video.status = VideoStatus.PROCESSING
        db.commit()
        
        # Video process et
        result = video_processor.process_video(video_path, video_id)
        
        # Database'e TÜMÜNÜ kaydet
        video.duration = int(result["duration"])
        video.processing_time = result.get("processing_time")
        video.fps_processed = result.get("fps_processed")
        video.detections_count = result.get("detections_count")
        video.landmarks_count = result.get("landmarks_count")
        video.top_objects = result.get("top_objects")
        video.extracted_texts = result.get("extracted_texts")
        video.vision_landmarks = result.get("vision_landmarks")
        video.transcription = result.get("transcription")
        video.extracted_locations = result.get("extracted_locations")
        video.enriched_locations = result.get("enriched_locations")
        video.deduplicated_locations = result.get("deduplicated_locations")
        video.location_summary = result.get("location_summary")
        video.optimized_route = result.get("optimized_route")
        video.travel_tips = result.get("travel_tips")
        video.ocr_pois = result.get("ocr_pois")
        video.status = VideoStatus.COMPLETED
        db.commit()
        
        logger.info(f".  Video {video_id} processed successfully!")
        logger.info(f"   AI Results:")
        logger.info(f"   - Detections: {result.get('detections_count')}")
        logger.info(f"   - Texts: {len(result.get('extracted_texts', []))}")
        logger.info(f"   - Processing: {result.get('processing_time')}s")
        
    except Exception as e:
        logger.error(f"❌ Video {video_id} processing failed: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.FAILED
            db.commit()
    
    finally:
        db.close()


    
@router.get("/{video_id}/progress")
async def get_video_progress(video_id: int, db: Session = Depends(get_db)):
    """
    Video işlem aşamasını döner (mobil polling için).
    stage: metadata | frames | ai_parallel | ner | geocoding | overpass | dedup | route | rag | done
    percent: 0-100
    """
    # Redis'ten progress bilgisini al
    if _progress_redis:
        try:
            raw = _progress_redis.get(f"progress:{video_id}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    # Fallback: DB'deki status'e göre tahmin
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, detail="Video not found")

    stage_map = {
        VideoStatus.UPLOADED:   ("uploaded",   5),
        VideoStatus.PROCESSING: ("processing", 30),
        VideoStatus.COMPLETED:  ("done",       100),
        VideoStatus.FAILED:     ("failed",     0),
    }
    stage, percent = stage_map.get(video.status, ("unknown", 0))
    return {"stage": stage, "percent": percent}


@router.get("/stats")
async def get_platform_stats(db: Session = Depends(get_db)):
    """Platform istatistikleri"""
    from sqlalchemy import func
    total_videos = db.query(func.count(Video.id)).scalar()
    completed = db.query(func.count(Video.id)).filter(Video.status == VideoStatus.COMPLETED).scalar()
    total_users = db.query(func.count(func.distinct(Video.user_id))).scalar()
    all_locations = db.query(Video.deduplicated_locations).filter(Video.deduplicated_locations.isnot(None)).all()
    city_names = set()
    for (locs,) in all_locations:
        if locs:
            for l in locs:
                city_names.add(l.get("original_name", "").lower())
    return {"total_videos": total_videos, "completed_videos": completed, "total_users": total_users, "total_cities": len(city_names)}


@router.get("/public")
async def get_public_plans(city: str = None, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """Public feed — completed videolar"""
    all_videos = db.query(Video).filter(Video.status == VideoStatus.COMPLETED).order_by(Video.created_at.desc()).all()
    plans = []
    for v in all_videos:
        locs = v.deduplicated_locations or []
        if city:
            names = [l.get("original_name", "").lower() for l in locs]
            if not any(city.lower() in n for n in names):
                continue
        plans.append({"id": v.id, "filename": v.filename, "duration": v.duration,
                       "created_at": v.created_at.isoformat() if v.created_at else None,
                       "locations_count": len(locs), "top_location": locs[0]["original_name"] if locs else None,
                       "ocr_preview": (v.extracted_texts or [])[:3], "processing_time": v.processing_time})
    return {"plans": plans[offset:offset + limit], "total": len(plans)}


@router.get("/user/{user_id}")
async def get_user_videos(user_id: int, db: Session = Depends(get_db)):
    """Kullanıcıya ait tüm videolar"""
    videos = db.query(Video).filter(Video.user_id == user_id).order_by(Video.created_at.desc()).all()
    plans = [{"id": v.id, "filename": v.filename, "status": v.status.value if v.status else "unknown",
               "duration": v.duration, "created_at": v.created_at.isoformat() if v.created_at else None,
               "locations_count": len(v.deduplicated_locations) if v.deduplicated_locations else 0,
               "top_location": v.deduplicated_locations[0]["original_name"] if v.deduplicated_locations else None,
               "ocr_preview": (v.extracted_texts or [])[:3], "processing_time": v.processing_time}
              for v in videos]
    return {"plans": plans, "total": len(plans)}


@router.get("/{video_id}")
async def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get video with AI results"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, detail="Video not found")
    
    data = {
        "id": video.id,
        "filename": video.filename,
        "status": video.status.value,
        "duration": video.duration,
        "created_at": video.created_at.isoformat(),
        "ai_results": {
            "processing_time": video.processing_time,
            "fps_processed": video.fps_processed,
            "detections": {
                "count": video.detections_count,
                "landmarks_count": video.landmarks_count,
                "top_objects": video.top_objects
            },
            "ocr": {
                "extracted_texts": video.extracted_texts
            },
            "vision": {
                "landmarks": video.vision_landmarks
            },
            "audio": {
                "transcription": video.transcription
            },
            "ner": {
                "extracted_locations": video.extracted_locations
            },
            "nominatim": {
                "enriched_locations": video.enriched_locations,
                "deduplicated_locations": video.deduplicated_locations,
                "location_summary": video.location_summary
            },
            "route": {
                "optimized_route": video.optimized_route
            },
            "rag": {
                "travel_tips": video.travel_tips
            },
            "ocr_pois": video.ocr_pois
        }
    }
    
    return JSONResponse(content=json.loads(json.dumps(data, ensure_ascii=False)))


