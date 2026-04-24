"""
Infrastructure katmanı — AbstractVideoRepository'nin SQLAlchemy implementasyonu.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.repositories.video_repository import AbstractVideoRepository
from app.models.video import Video, VideoStatus


class SqlVideoRepository(AbstractVideoRepository):

    def __init__(self, db: Session):
        self._db = db

    def create(self, filename: str, file_path: str, user_id: int) -> Video:
        video = Video(
            filename=filename,
            file_path=file_path,
            status=VideoStatus.UPLOADED,
            user_id=user_id,
        )
        self._db.add(video)
        self._db.commit()
        self._db.refresh(video)
        return video

    def get_by_id(self, video_id: int) -> Optional[Video]:
        return self._db.query(Video).filter(Video.id == video_id).first()

    def get_by_user(self, user_id: int) -> List[Video]:
        return (
            self._db.query(Video)
            .filter(Video.user_id == user_id)
            .order_by(Video.created_at.desc())
            .all()
        )

    def get_completed(
        self,
        city: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        all_videos = (
            self._db.query(Video)
            .filter(Video.status == VideoStatus.COMPLETED)
            .order_by(Video.created_at.desc())
            .all()
        )
        plans = []
        for v in all_videos:
            locs = v.deduplicated_locations or []
            if city:
                names = [loc.get("original_name", "").lower() for loc in locs]
                if not any(city.lower() in n for n in names):
                    continue
            plans.append({
                "id": v.id,
                "filename": v.filename,
                "duration": v.duration,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "locations_count": len(locs),
                "top_location": locs[0]["original_name"] if locs else None,
                "ocr_preview": (v.extracted_texts or [])[:3],
                "processing_time": v.processing_time,
            })
        return {"plans": plans[offset: offset + limit], "total": len(plans)}

    def get_stats(self) -> Dict[str, int]:
        total_videos = self._db.query(func.count(Video.id)).scalar()
        completed = (
            self._db.query(func.count(Video.id))
            .filter(Video.status == VideoStatus.COMPLETED)
            .scalar()
        )
        total_users = self._db.query(func.count(func.distinct(Video.user_id))).scalar()

        all_locs = (
            self._db.query(Video.deduplicated_locations)
            .filter(Video.deduplicated_locations.isnot(None))
            .all()
        )
        city_names: set = set()
        for (locs,) in all_locs:
            if locs:
                for loc in locs:
                    city_names.add(loc.get("original_name", "").lower())

        return {
            "total_videos": total_videos,
            "completed_videos": completed,
            "total_users": total_users,
            "total_cities": len(city_names),
        }

    def mark_processing(self, video_id: int) -> None:
        video = self.get_by_id(video_id)
        if video:
            video.status = VideoStatus.PROCESSING
            self._db.commit()

    def save_results(self, video_id: int, results: Dict[str, Any]) -> None:
        video = self.get_by_id(video_id)
        if not video:
            return
        video.duration          = int(results.get("duration", 0))
        video.processing_time   = results.get("processing_time")
        video.fps_processed     = results.get("fps_processed")
        video.detections_count  = results.get("detections_count")
        video.landmarks_count   = results.get("landmarks_count")
        video.top_objects       = results.get("top_objects")
        video.extracted_texts   = results.get("extracted_texts")
        video.vision_landmarks  = results.get("vision_landmarks")
        video.transcription     = results.get("transcription")
        video.extracted_locations   = results.get("extracted_locations")
        video.enriched_locations    = results.get("enriched_locations")
        video.deduplicated_locations = results.get("deduplicated_locations")
        video.location_summary  = results.get("location_summary")
        video.optimized_route   = results.get("optimized_route")
        video.travel_tips       = results.get("travel_tips")
        video.ocr_pois          = results.get("ocr_pois")
        video.status            = VideoStatus.COMPLETED
        self._db.commit()

    def mark_failed(self, video_id: int) -> None:
        video = self.get_by_id(video_id)
        if video:
            video.status = VideoStatus.FAILED
            self._db.commit()
