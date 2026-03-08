from fastapi import APIRouter,UploadFile,File,HTTPException
import httpx
import os

router = APIRouter(prefix="/videos",tags =["videos"])

CORE_API_URL = os.getenv("CORE_API_URL","http://core-api:8000")

@router.post("/upload")
async def upload_video(file:UploadFile=File(...)):
    """
    Mobile video upload endpoint
    - Validates video file
    - Forwards to Core API
    - Returns minimal response for mobile
    """

    #Validate
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(400,detail="File must be a video")
    
    # File Size Check
    content = await file.read()
    if len(content)>100 *1024*1024:
        raise HTTPException(400,detail="Video too large (max 100MB)")
    
    #Forward to Core API

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file.filename, content, file.content_type)}
            response = await client.post(
                f"{CORE_API_URL}/internal/videos/process",
                files= files
            )

            response.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(500,detail=f"CORE API Error: {str(e)}")
    
    data = response.json()

    # Mobile -optimized response

    return{
        "id": data["id"],
        "status": data["status"],
        "message": "Video uploaded succesfully"
    }

@router.get("/{video_id}")
async def get_video_status(video_id:int):
    """ Get video processing status"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CORE_API_URL}/internal/videos/{video_id}"
        )
    if response.status_code==404:
        raise HTTPException(404,detail="Video not found")

    return response.json()