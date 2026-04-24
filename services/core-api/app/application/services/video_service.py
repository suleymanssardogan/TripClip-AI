"""
Application katmanı — Video iş mantığı.
Repository ve ML processor DI ile enjekte edilir → test ortamında kolayca mock'lanır.
"""
from fastapi import HTTPException
from pathlib import Path
from typing import Optional, Dict, Any
import uuid
import os
import logging

from app.domain.repositories.video_repository import AbstractVideoRepository
from app.application.dto.video_dto import (
    VideoUploadResponse,
    ProgressResponse,
    PlanListResponse,
    StatsResponse,
    VideoDetailResponse,
    PlanSummary,
)
from app.models.video import VideoStatus

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads/videos"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class VideoService:

    def __init__(self, video_repo: AbstractVideoRepository):
        self._repo = video_repo

    # ── Upload ────────────────────────────────────────────────────────────────

    def create_upload(self, filename: str, content: bytes, user_id: int) -> tuple[int, Path]:
        """
        Dosyayı diske yazar, DB kaydı oluşturur.
        (video_id, file_path) döner — background task bu bilgiyle ML çalıştırır.
        """
        ext       = Path(filename).suffix or ".mp4"
        file_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
        file_path.write_bytes(content)

        video = self._repo.create(
            filename=filename,
            file_path=str(file_path),
            user_id=user_id,
        )
        return video.id, file_path

    def build_upload_response(self, video_id: int, filename: str) -> VideoUploadResponse:
        return VideoUploadResponse(
            id=video_id,
            filename=filename,
            status=VideoStatus.UPLOADED.value,
            message="Video uploaded! Processing started in background.",
        )

    # ── Progress ──────────────────────────────────────────────────────────────

    def get_progress(self, video_id: int, redis_client=None) -> ProgressResponse:
        """Redis varsa oradan, yoksa DB status'ten tahmin ederek döner."""
        if redis_client:
            try:
                import json
                raw = redis_client.get(f"progress:{video_id}")
                if raw:
                    data = json.loads(raw)
                    return ProgressResponse(stage=data["stage"], percent=data["percent"])
            except Exception:
                pass

        video = self._repo.get_by_id(video_id)
        if not video:
            raise HTTPException(404, detail="Video not found")

        stage_map = {
            VideoStatus.UPLOADED:   ("uploaded",   5),
            VideoStatus.PROCESSING: ("processing", 30),
            VideoStatus.COMPLETED:  ("done",       100),
            VideoStatus.FAILED:     ("failed",     0),
        }
        stage, percent = stage_map.get(video.status, ("unknown", 0))
        return ProgressResponse(stage=stage, percent=percent)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_stats(self) -> StatsResponse:
        data = self._repo.get_stats()
        return StatsResponse(**data)

    def get_public_feed(
        self,
        city: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PlanListResponse:
        data = self._repo.get_completed(city=city, limit=limit, offset=offset)
        plans = [PlanSummary(
            status="completed",
            **{k: v for k, v in p.items()}
        ) for p in data["plans"]]
        return PlanListResponse(plans=plans, total=data["total"])

    def get_user_videos(self, user_id: int) -> PlanListResponse:
        videos = self._repo.get_by_user(user_id)
        plans = [
            PlanSummary(
                id=v.id,
                filename=v.filename,
                status=v.status.value if v.status else "unknown",
                duration=v.duration,
                created_at=v.created_at.isoformat() if v.created_at else None,
                locations_count=len(v.deduplicated_locations) if v.deduplicated_locations else 0,
                top_location=(v.deduplicated_locations or [{}])[0].get("original_name") if v.deduplicated_locations else None,
                ocr_preview=(v.extracted_texts or [])[:3],
                processing_time=v.processing_time,
            )
            for v in videos
        ]
        return PlanListResponse(plans=plans, total=len(plans))

    def get_video_detail(self, video_id: int) -> VideoDetailResponse:
        video = self._repo.get_by_id(video_id)
        if not video:
            raise HTTPException(404, detail="Video not found")

        return VideoDetailResponse(
            id=video.id,
            filename=video.filename,
            status=video.status.value,
            duration=video.duration,
            created_at=video.created_at.isoformat(),
            ai_results={
                "processing_time":  video.processing_time,
                "fps_processed":    video.fps_processed,
                "detections": {
                    "count":           video.detections_count,
                    "landmarks_count": video.landmarks_count,
                    "top_objects":     video.top_objects,
                },
                "ocr":    {"extracted_texts": video.extracted_texts},
                "vision": {"landmarks": video.vision_landmarks},
                "audio":  {"transcription": video.transcription},
                "ner":    {"extracted_locations": video.extracted_locations},
                "nominatim": {
                    "enriched_locations":    video.enriched_locations,
                    "deduplicated_locations": video.deduplicated_locations,
                    "location_summary":      video.location_summary,
                },
                "route":    {"optimized_route": video.optimized_route},
                "rag":      {"travel_tips": video.travel_tips},
                "ocr_pois": video.ocr_pois,
            },
        )
