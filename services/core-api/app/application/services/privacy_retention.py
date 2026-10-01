"""Bounded raw-upload cleanup; completed plans remain until user deletion."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import or_, and_
from app.models.video import Video, VideoStatus
from app.models.privacy_erasure_record import PrivacyErasureRecord, PendingFileErasure


def purge_expired_uploads(db, upload_root=None, now=None):
    now = now or datetime.utcnow()
    root = Path(upload_root or os.getenv("UPLOAD_DIR", "/tmp/uploads/videos")).resolve()
    completed_hours = int(os.getenv("RAW_UPLOAD_RETENTION_HOURS", "24"))
    failed_hours = int(os.getenv("FAILED_UPLOAD_RETENTION_HOURS", "168"))
    if not 1 <= completed_hours <= 720 or not 1 <= failed_hours <= 720:
        raise ValueError("Raw upload retention must be between 1 and 720 hours")
    rows = db.query(Video).filter(Video.file_path != "", or_(
        and_(Video.status == VideoStatus.COMPLETED, Video.created_at < now - timedelta(hours=completed_hours)),
        and_(Video.status == VideoStatus.FAILED, Video.created_at < now - timedelta(hours=failed_hours)),
    )).order_by(Video.created_at).limit(100).with_for_update(skip_locked=True).all()
    count = 0
    for job in db.query(PendingFileErasure).order_by(PendingFileErasure.created_at).limit(100).with_for_update(skip_locked=True).all():
        path = Path(job.file_path).resolve()
        if not path.is_relative_to(root) or path == root:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
        db.delete(job)
        count += 1
    for video in rows:
        path = Path(video.file_path).resolve()
        if not path.is_relative_to(root) or path == root:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue  # Keep the path so the next sweep retries failed deletion.
        video.file_path = ""
        count += 1
    if count:
        db.add(PrivacyErasureRecord(action="destroy", category="raw_video_upload", count=count, performed_at=now))
        db.commit()
    # Keep destruction evidence for at least three calendar years (leap-safe).
    try:
        cutoff = now.replace(year=now.year - 3)
    except ValueError:
        cutoff = now.replace(year=now.year - 3, day=28)
    db.query(PrivacyErasureRecord).filter(PrivacyErasureRecord.performed_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return count


def sweep_upload_retention():
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        return purge_expired_uploads(db)
