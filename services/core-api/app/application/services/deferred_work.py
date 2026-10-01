"""SQL outbox, leased execution, bounded retry. No payload contains user text."""
from datetime import datetime, timedelta
import logging
from sqlalchemy import and_, or_
from sqlalchemy import func
from prometheus_client import Gauge
from app.models.deferred_job import DeferredJob

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
LEASE_SECONDS = 900
DEFERRED_JOBS = Gauge("ai_deferred_jobs", "Durable AI jobs awaiting work or operator attention", ["status"])


def enqueue(db, kind, entity_id):
    job = DeferredJob(kind=kind, entity_id=entity_id)
    db.add(job)
    return job  # Caller owns commit: work and business state commit together.


def dispatch_due(db, publish, limit=20, now=None):
    now = now or datetime.utcnow()
    old_ids = [r[0] for r in db.query(DeferredJob.id).filter(
        DeferredJob.status == "completed", DeferredJob.completed_at < now - timedelta(days=7)
    ).order_by(DeferredJob.id).limit(100).all()]
    if old_ids:
        db.query(DeferredJob).filter(DeferredJob.id.in_(old_ids)).delete(synchronize_session=False)
        db.commit()
    eligible = (
        DeferredJob.status.in_(["pending", "queued", "processing"]),
        DeferredJob.available_at <= now,
        or_(DeferredJob.lease_until.is_(None), DeferredJob.lease_until <= now),
    )
    db.query(DeferredJob).filter(*eligible, DeferredJob.attempts >= MAX_ATTEMPTS).update(
        {"status": "failed", "lease_until": None}, synchronize_session=False)
    db.commit()
    # A worker can die on its final attempt without reaching execute_job's
    # exception handler. Reconcile exhausted main jobs with the video state.
    from app.models.video import Video, VideoStatus
    exhausted = db.query(DeferredJob.entity_id).filter(
        DeferredJob.kind == "video_analysis", DeferredJob.status == "failed")
    db.query(Video).filter(Video.id.in_(exhausted), Video.status != VideoStatus.COMPLETED).update(
        {"status": VideoStatus.FAILED}, synchronize_session=False)
    db.commit()
    counts = dict(db.query(DeferredJob.status, func.count(DeferredJob.id)).filter(
        DeferredJob.status != "completed").group_by(DeferredJob.status).all())
    for status in ("pending", "queued", "processing", "failed"):
        DEFERRED_JOBS.labels(status=status).set(counts.get(status, 0))
    ids = [r[0] for r in db.query(DeferredJob.id).filter(*eligible)
           .order_by(DeferredJob.id).limit(limit).all()]
    sent = 0
    for job_id in ids:
        # Multiple API replicas may dispatch. Reserve an interval atomically;
        # a crash at any point only delays the next dispatch, never loses work.
        reserved = db.query(DeferredJob).filter(DeferredJob.id == job_id, *eligible).update(
            {"status": "queued", "lease_until": None,
             "available_at": now + timedelta(seconds=60)}, synchronize_session=False)
        db.commit()
        if not reserved:
            continue
        try:
            publish(job_id)
            sent += 1
        except Exception as exc:
            logger.warning("Outbox broker unavailable | error=%s", type(exc).__name__)
            break  # One bounded probe per outage; do not stall on every row.
    return sent


def execute_job(db, job_id, handler, now=None):
    now = now or datetime.utcnow()
    lease = now + timedelta(seconds=LEASE_SECONDS)
    claimed = db.query(DeferredJob).filter(
        DeferredJob.id == job_id,
        or_(DeferredJob.status == "queued",
            and_(DeferredJob.status == "pending", DeferredJob.available_at <= now),
            DeferredJob.status == "processing"),
        DeferredJob.attempts < MAX_ATTEMPTS,
        or_(DeferredJob.lease_until.is_(None), DeferredJob.lease_until <= now),
    ).update({"status": "processing", "lease_until": lease,
              "attempts": DeferredJob.attempts + 1}, synchronize_session=False)
    db.commit()
    if not claimed:
        return "skipped"
    job = db.query(DeferredJob).filter_by(id=job_id).one()
    attempts = job.attempts
    try:
        handler(job.kind, job.entity_id)
    except Exception as exc:
        db.rollback()
        status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        db.query(DeferredJob).filter_by(id=job_id, status="processing", lease_until=lease).update({
            "status": status, "lease_until": None,
            "available_at": now + timedelta(seconds=min(30 * 2 ** (attempts - 1), 3600)),
            "last_error": type(exc).__name__,
        }, synchronize_session=False)
        if job.kind == "video_analysis":
            from app.models.video import Video, VideoStatus
            db.query(Video).filter(Video.id == job.entity_id, Video.status != VideoStatus.COMPLETED).update(
                {"status": VideoStatus.FAILED if status == "failed" else VideoStatus.UPLOADED}, synchronize_session=False)
        db.commit()
        logger.warning("Deferred work retry | job_id=%s | kind=%s | status=%s", job_id, job.kind, status)
        return status
    db.query(DeferredJob).filter_by(id=job_id, status="processing", lease_until=lease).update({
        "status": "completed", "completed_at": datetime.utcnow(),
        "lease_until": None, "last_error": None,
    }, synchronize_session=False)
    db.commit()
    return "completed"


def dispatch_pending_work():
    from app.core.database import SessionLocal
    from app.tasks.video_tasks import deferred_work_task, durable_analysis_task
    with SessionLocal() as db:
        def publish(job_id):
            job = db.get(DeferredJob, job_id)
            task = durable_analysis_task if job.kind == "video_analysis" else deferred_work_task
            task.apply_async(args=[job_id], ignore_result=True, retry=False)
        return dispatch_due(db, publish)
