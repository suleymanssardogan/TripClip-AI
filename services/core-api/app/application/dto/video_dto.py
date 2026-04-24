"""
Video DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ── Response DTO'ları ─────────────────────────────────────────────────────────

class VideoUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str


class ProgressResponse(BaseModel):
    stage: str
    percent: int


class PlanSummary(BaseModel):
    """Public feed veya kullanıcı listesi için özet."""
    id: int
    filename: str
    status: str
    duration: Optional[int]
    created_at: Optional[str]
    locations_count: int
    top_location: Optional[str]
    ocr_preview: List[str]
    processing_time: Optional[float]


class PlanListResponse(BaseModel):
    plans: List[PlanSummary]
    total: int


class StatsResponse(BaseModel):
    total_videos: int
    completed_videos: int
    total_users: int
    total_cities: int


class VideoDetailResponse(BaseModel):
    """Tek video — tam AI sonuçlarıyla."""
    id: int
    filename: str
    status: str
    duration: Optional[int]
    created_at: str
    ai_results: Dict[str, Any]
