from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.video import Video, VideoStatus
from app.core.services.video_processor import VideoProcessingService
import uuid
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/videos", tags=["internal"])

UPLOAD_DIR = Path("/app/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

video_processor = VideoProcessingService()


@router.post("/process")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
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
        user_id=1  # TODO: Get from auth
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
    """Background task: Video işleme"""
    
    # Yeni DB session (background task için)
    from app.core.database import SessionLocal
    db = SessionLocal()
    
    try:
        logger.info(f"🎬 Starting background processing for video {video_id}")
        
        # Status güncelle: PROCESSING
        video = db.query(Video).filter(Video.id == video_id).first()
        video.status = VideoStatus.PROCESSING
        db.commit()
        
        # Video process et
        result = video_processor.process_video(video_path, video_id)
        
        # Duration güncelle
        video.duration = int(result["duration"])
        video.status = VideoStatus.COMPLETED
        db.commit()
        
        logger.info(f" Video {video_id} processed successfully!")
        logger.info(f"   Duration: {result['duration']}s")
        logger.info(f"   Resolution: {result['resolution']}")
        logger.info(f"   Frames: {result['frame_count']}")
        
    except Exception as e:
        logger.error(f"Video {video_id} processing failed: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = VideoStatus.FAILED
            db.commit()
    
    finally:
        db.close()


@router.get("/{video_id}")
async def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get video details"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, detail="Video not found")
    
    return {
        "id": video.id,
        "filename": video.filename,
        "status": video.status.value,
        "duration": video.duration,
        "created_at": video.created_at.isoformat()
    }