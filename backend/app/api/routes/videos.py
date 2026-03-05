from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.video import Video, VideoStatus
import uuid
import os
from pathlib import Path

router = APIRouter(prefix="/api/videos", tags=["videos"])

UPLOAD_DIR = Path("uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validate
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "File must be a video")
    
    # Save file
    video_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{video_id}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Save to database
    db_video = Video(
        filename=file.filename,
        file_path=str(file_path),
        status=VideoStatus.UPLOADED
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    return {
        "id": db_video.id,
        "filename": db_video.filename,
        "status": db_video.status,
        "created_at": db_video.created_at
    }

@router.get("/{video_id}")
async def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    return video

@router.get("/")
async def list_videos(db: Session = Depends(get_db)):
    videos = db.query(Video).all()
    return videos