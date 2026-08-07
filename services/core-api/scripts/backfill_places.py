"""
Tek seferlik backfill — mevcut (bu migration'dan ÖNCE tamamlanmış) videoların
`deduplicated_locations` JSON'ını videolar-arası Place kütüphanesine işler.

Yeni tamamlanan videolar için bu adım artık otomatik (bkz.
SqlVideoRepository.save_results → SqlPlaceRepository.sync_from_video); bu
script SADECE geçmişteki videoları bir kerelik doldurmak için var.

Çalıştırma:
    cd services/core-api
    python -m scripts.backfill_places
    # ya da container içinden:
    docker compose exec core-api python -m scripts.backfill_places
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_places")


def run() -> None:
    from app.core.database import SessionLocal
    from app.models.video import Video, VideoStatus
    from app.infrastructure.repositories.sql_place_repository import SqlPlaceRepository

    db = SessionLocal()
    try:
        videos = (
            db.query(Video)
            .filter(Video.status == VideoStatus.COMPLETED)
            .filter(Video.deduplicated_locations.isnot(None))
            .all()
        )
        logger.info("🔎 %d tamamlanmış video bulundu, işleniyor...", len(videos))

        place_repo = SqlPlaceRepository(db)
        processed, skipped = 0, 0
        for video in videos:
            if not video.user_id:
                skipped += 1
                continue
            try:
                place_repo.sync_from_video(video)
                processed += 1
            except Exception:
                logger.exception("⚠️ Video atlandı | video_id=%s", video.id)
                db.rollback()

        logger.info("✅ Backfill tamamlandı | işlenen=%d | atlanan (sahipsiz)=%d",
                     processed, skipped)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("❌ Backfill başarısız")
        sys.exit(1)
