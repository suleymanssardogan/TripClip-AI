from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.video import Video, VideoStatus
import uuid
from pathlib import Path

router = APIRouter(prefix="/internal/videos", tags=["internal"])

UPLOAD_DIR = Path("/app/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/process")
async def process_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Internal endpoint - called by BFFs
    Saves video and starts processing
    """
    
    # Generate unique filename
    video_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{video_id}{file_extension}"
    
    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Save to database
    db_video = Video(
        filename=file.filename,
        file_path=str(file_path),
        status=VideoStatus.UPLOADED,
        user_id=1  # TODO: Get from auth
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    return {
        "id": db_video.id,
        "filename": db_video.filename,
        "status": db_video.status.value,
        "created_at": db_video.created_at.isoformat()
    }

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
        "created_at": video.created_at.isoformat()
    }
