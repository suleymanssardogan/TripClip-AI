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

@router.get("/{video_id}")
async def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get video with AI results"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, detail="Video not found")
    
    return {
        "id": video.id,
        "filename": video.filename,
        "status": video.status.value,
        "duration": video.duration,
        "created_at": video.created_at.isoformat(),
        # AI Results
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
            "ner":{
                "extracted_locations": video.extracted_locations
            },
            "nominatim":{
                    "enriched_locations": video.enriched_locations,
                    "deduplicated_locations":video.deduplicated_locations,
                    "location_summary":video.location_summary
            },
            "route": {
                "optimized_route": video.optimized_route
            },
            "rag": {
                "travel_tips": video.travel_tips
            }

            
        }
    }