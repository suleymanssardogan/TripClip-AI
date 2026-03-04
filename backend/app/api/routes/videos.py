
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/videos", tags=["videos"])

# Temporary in-memory storage (DB sonra)
videos_db = {}

class VideoResponse(BaseModel):
    id: str
    filename: str
    status: str
    uploaded_at: str

@router.post("/upload", response_model=VideoResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload a video for processing"""
    
    # Validate file type
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "File must be a video")
    
    # Generate unique ID
    video_id = str(uuid.uuid4())
    
    # Save video metadata (simulated)
    video_data = {
        "id": video_id,
        "filename": file.filename,
        "status": "uploaded",
        "uploaded_at": datetime.now().isoformat()
    }
    
    videos_db[video_id] = video_data
    
    return video_data

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str):
    """Get video status"""
    
    if video_id not in videos_db:
        raise HTTPException(404, "Video not found")
    
    return videos_db[video_id]

@router.get("/", response_model=list[VideoResponse])
async def list_videos():
    """List all videos"""
    return list(videos_db.values())
