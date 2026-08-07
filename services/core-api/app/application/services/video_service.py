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
from app.models.video import VideoStatus, visible_locations
from app.core.exceptions import (
    VideoNotFoundException,
    PermissionDeniedException,
    InvalidStopOrderException,
)
from app.core.analytics_events import AnalyticsEvent
from app.application.services.analytics_service import AnalyticsService, get_analytics_service

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads/videos"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class VideoService:

    def __init__(self, video_repo: AbstractVideoRepository, analytics: Optional[AnalyticsService] = None):
        self._repo = video_repo
        self._analytics = analytics or get_analytics_service()

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

    # Kaç saniye geçtikten sonra "takılı kaldı" sayılır
    _STALE_THRESHOLD_SECONDS = 600  # 10 dakika

    def get_progress(self, video_id: int, redis_client=None) -> ProgressResponse:
        """
        İlerleme durumunu döner.

        - Redis varsa oradan okur (gerçek zamanlı %)
        - elapsed_seconds: sunucu tarafından hesaplanır → iOS'ta
          client-side timestamp hatası (7d bug) olmaz
        - stale=True: video 10 dk+ takılıysa → iOS hata ekranı gösterir
        """
        from datetime import datetime, timezone

        video = self._repo.get_by_id(video_id)
        if not video:
            raise HTTPException(404, detail="Video not found")

        # Geçen süre — created_at'tan değil, processing_started_at'a yakın
        # bir referans noktasından hesapla. DB'de işlem başlangıcı yok,
        # bu yüzden şimdi ile created_at arası değil; client'a "gerçek" süreyi
        # veriyoruz ama iOS kendi startDate'ini kullanmalı (aşağıdaki notta açıklandı).
        now_utc = datetime.now(timezone.utc)
        created = video.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = int((now_utc - created).total_seconds()) if created else 0

        # Redis'ten gerçek zamanlı veri dene
        if redis_client:
            try:
                import json
                raw = redis_client.get(f"progress:{video_id}")
                if raw:
                    data = json.loads(raw)
                    return ProgressResponse(
                        stage=data["stage"],
                        percent=data["percent"],
                        elapsed_seconds=elapsed,
                        stale=False,
                    )
            except Exception:
                pass

        stage_map = {
            VideoStatus.UPLOADED:   ("uploaded",    5),
            VideoStatus.PROCESSING: ("processing", 30),
            VideoStatus.COMPLETED:  ("done",       100),
            VideoStatus.FAILED:     ("failed",      0),
        }
        stage, percent = stage_map.get(video.status, ("unknown", 0))

        # Takılı video tespiti — uploaded/processing + eşik aşıldı
        stuck_stages = {VideoStatus.UPLOADED, VideoStatus.PROCESSING}
        is_stale = (
            video.status in stuck_stages
            and elapsed > self._STALE_THRESHOLD_SECONDS
        )
        if is_stale:
            stage   = "stale"
            percent = 0
            logger.warning("⚠️ Takılı video | video_id=%s | elapsed=%ds", video_id, elapsed)

        return ProgressResponse(
            stage=stage,
            percent=percent,
            elapsed_seconds=elapsed,
            stale=is_stale,
        )

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

        def _summary(v) -> PlanSummary:
            # Kullanıcının düzenlediği hâli — ham AI listesi değil. Aksi hâlde
            # liste kartı "12 mekan" derken detay ekranı 11 gösteriyordu.
            locs = visible_locations(v)
            return PlanSummary(
                id=v.id,
                filename=v.filename,
                status=v.status.value if v.status else "unknown",
                duration=v.duration,
                created_at=v.created_at.isoformat() if v.created_at else None,
                locations_count=len(locs),
                top_location=locs[0].get("original_name") if locs else None,
                ocr_preview=(v.extracted_texts or [])[:3],
                processing_time=v.processing_time,
            )

        plans = [_summary(v) for v in videos]
        return PlanListResponse(plans=plans, total=len(plans))

    def get_video_detail(self, video_id: int, requesting_user_id: Optional[int] = None) -> VideoDetailResponse:
        video = self._repo.get_by_id(video_id)
        if not video:
            raise HTTPException(404, detail="Video not found")

        is_owner = requesting_user_id is not None and video.user_id == requesting_user_id
        is_completed = video.status == VideoStatus.COMPLETED

        # Non-owners can only access completed (shareable) videos.
        # Return 404 rather than 403 to avoid leaking video existence to third parties.
        if not is_owner and not is_completed:
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
            degradation=video.degradation,
            stop_order=video.stop_order,
        )

    # ── Editor ────────────────────────────────────────────────────────────────

    def update_stop_order(self, video_id: int, user_id: int, order: list[list[int]]) -> None:
        """
        Editor'de kullanıcının belirlediği durak sırasını kaydeder.
        Sahiplik repo katmanında doğrulanır.

        `order` hem sıralamayı hem de HANGİ durakların kalacağını belirler:
        listede olmayan bir durak kullanıcı tarafından silinmiş sayılır. Bu
        yüzden id'lerin gerçekten var olan duraklara işaret etmesi ve
        tekrarlanmaması şart — aksi halde okuma tarafındaki eşleme sessizce
        durak kaybeder ya da çoğaltır.
        """
        existing = self._repo.get_by_id(video_id)
        if existing is None:
            raise VideoNotFoundException(video_id)
        if existing.user_id != user_id:
            raise PermissionDeniedException("Bu videoyu düzenleme yetkiniz yok.")

        valid_ids = set(range(1, len(existing.deduplicated_locations or []) + 1))
        flat = [stop_id for day in order for stop_id in day]

        unknown = sorted(set(flat) - valid_ids)
        if unknown:
            raise InvalidStopOrderException(f"Geçersiz durak numarası: {unknown}.")
        if len(flat) != len(set(flat)):
            raise InvalidStopOrderException("Aynı durak birden fazla kez sıralanamaz.")

        self._repo.update_stop_order(video_id, user_id, order)

    def delete_video(self, video_id: int, user_id: int) -> None:
        """
        Videoyu ve diskteki dosyasını kalıcı olarak siler.

        Dosya silme best-effort: DB kaydı gittikten sonra dosya kalırsa bu
        yalnızca yer kaybıdır, ama dosya silinip DB kaydı kalsaydı kullanıcı
        açılmayan bir plan görürdü. O yüzden sıra bu şekilde.
        """
        file_path = self._repo.delete(video_id, user_id)
        if file_path is None:
            existing = self._repo.get_by_id(video_id)
            if existing is None:
                raise VideoNotFoundException(video_id)
            raise PermissionDeniedException("Bu videoyu silme yetkiniz yok.")

        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Video dosyası silinemedi | video_id=%s | %s", video_id, exc)

        # AnalyticsService.track kendi içinde best-effort (asla fırlatmaz) —
        # silme işlemi zaten tamamlanmış durumda, ayrıca try/except gerekmiyor.
        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_DELETED,
            trip_id=video_id,
            platform="server",
            user_id=user_id,
            source="user_delete",
        )
