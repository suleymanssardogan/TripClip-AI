import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytest

if os.getenv("TRIPCLIP_INTEGRATION") != "1":
    pytest.skip("Run scripts/test-integration.sh for real infrastructure tests", allow_module_level=True)

from sqlalchemy import text
from app.core.database import engine
from app.core.video_claim import analysis_claim
from app.application.services.deferred_work import dispatch_pending_work
from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
from app.models.video import Video, VideoStatus
from app.models.deferred_job import DeferredJob
from integration.conftest import eventually


def create_video(database, payload=b"fast"):
    root = Path(os.environ["UPLOAD_DIR"]); root.mkdir(parents=True, exist_ok=True)
    path = root / f"{time.time_ns()}.mp4"; path.write_bytes(payload)
    with database() as db:
        video = SqlVideoRepository(db).create(path.name, str(path), 1)
        job = db.query(DeferredJob).filter_by(entity_id=video.id, kind="video_analysis").one()
        return video.id, job.id, path


def status(database, job_id):
    with database() as db:
        return db.get(DeferredJob, job_id).status


def runs(video_id):
    with engine.connect() as db:
        return db.execute(text("SELECT count(*) FROM integration_runs WHERE video_id=:id"), {"id": video_id}).scalar()


def redispatch(database, job_id):
    # Accelerate the clock, not the implementation: production lease is 900s.
    with database() as db:
        job = db.get(DeferredJob, job_id)
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        job.lease_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    dispatch_pending_work()


def test_postgres_lock_excludes_second_connection_and_releases(database):
    with analysis_claim(42, engine) as first:
        assert first
        with analysis_claim(42, engine) as second:
            assert not second
    with analysis_claim(42, engine) as next_owner:
        assert next_owner


def test_real_worker_completes_and_duplicate_message_does_not_repeat_analysis(database, workers):
    from app.tasks.video_tasks import durable_analysis_task
    workers[0]()
    vid, job, _ = create_video(database)
    dispatch_pending_work()
    eventually(lambda: status(database, job) == "completed")
    assert runs(vid) == 1
    duplicate = durable_analysis_task.apply_async(args=[job])
    assert duplicate.get(timeout=15) == "skipped"
    assert runs(vid) == 1
    with database() as db:
        assert db.get(Video, vid).status == VideoStatus.COMPLETED


def test_redis_network_outage_preserves_job_then_recovers(database, proxy, workers):
    vid, job, _ = create_video(database)
    proxy("redis", False)
    dispatch_pending_work()  # Actual broker publication fails; SQL row survives.
    with database() as db:
        assert db.get(Video, vid) is not None
        assert db.get(DeferredJob, job).status == "queued"
        assert db.get(DeferredJob, job).attempts == 0
    proxy("redis", True)
    workers[0]()
    redispatch(database, job)
    eventually(lambda: status(database, job) == "completed")
    assert runs(vid) == 1


def test_killed_worker_is_recovered_from_sql_lease(database, workers):
    start, kill = workers
    process = start()
    vid, job, path = create_video(database, b"slow")
    dispatch_pending_work()
    eventually(lambda: runs(vid) == 1)
    kill(process)
    assert status(database, job) == "processing"
    # New worker cannot bypass an active SQL lease.
    start()
    from app.tasks.video_tasks import durable_analysis_task
    assert durable_analysis_task.apply_async(args=[job]).get(timeout=15) == "skipped"
    path.write_bytes(b"fast")
    redispatch(database, job)
    eventually(lambda: status(database, job) == "completed")
    assert runs(vid) == 2
    with database() as db:
        assert db.get(DeferredJob, job).attempts == 2
        assert db.get(Video, vid).status == VideoStatus.COMPLETED


def test_qdrant_outage_retries_real_index_job(database, proxy, workers):
    from app.models.place import Place
    from app.application.services.deferred_work import enqueue
    from qdrant_client import QdrantClient
    workers[0]()
    with database() as db:
        place = Place(name="Synthetic Museum", name_key="synthetic museum", lat=41, lng=29, city="Istanbul")
        db.add(place); db.flush()
        job = enqueue(db, "place_index", place.id); db.commit()
        job_id, place_id = job.id, place.id
    proxy("qdrant", False)
    dispatch_pending_work()
    eventually(lambda: status(database, job_id) == "pending")
    with database() as db:
        assert db.get(DeferredJob, job_id).attempts == 1
    proxy("qdrant", True)
    redispatch(database, job_id)
    eventually(lambda: status(database, job_id) == "completed")
    client = QdrantClient(url=os.environ["QDRANT_URL"], timeout=3)
    try:
        assert client.retrieve("places", ids=[place_id])[0].id == place_id
    finally:
        client.close()


def test_postgres_connection_death_releases_analysis_lock(database):
    from sqlalchemy.exc import DBAPIError
    connection = engine.connect()
    try:
        backend_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar()
        assert connection.execute(text("SELECT pg_try_advisory_xact_lock(73419, 43)")).scalar()
        with engine.begin() as admin:
            assert admin.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": backend_pid}).scalar()
        with analysis_claim(43, engine) as acquired:
            assert acquired
    finally:
        try:
            connection.close()
        except DBAPIError:
            connection.invalidate()


def test_postgres_video_and_outbox_rollback_together(database, monkeypatch):
    import app.application.services.deferred_work as work
    def fail(*args):
        raise RuntimeError("synthetic outbox failure")
    monkeypatch.setattr(work, "enqueue", fail)
    with database() as db:
        with pytest.raises(RuntimeError):
            SqlVideoRepository(db).create("rollback.mp4", "/tmp/nonexistent", 1)
        assert db.query(Video).count() == 0
        assert db.query(DeferredJob).count() == 0


def test_maintenance_dispatch_and_retention_without_api(database, workers, maintenance):
    workers[0]()
    vid, job, _ = create_video(database)
    root = Path(os.environ["UPLOAD_DIR"])
    old_path = root / "expired.mp4"; old_path.write_bytes(b"old-private-video")
    with database() as db:
        db.add(Video(filename="expired.mp4", file_path=str(old_path), user_id=1,
                     status=VideoStatus.COMPLETED, created_at=datetime.utcnow() - timedelta(days=2)))
        db.commit()
    process, health_dir = maintenance()
    # No API process and no explicit dispatch/retention call in this test.
    eventually(lambda: status(database, job) == "completed")
    eventually(lambda: not old_path.exists())
    assert runs(vid) == 1
    process.terminate(); assert process.wait(timeout=15) == 0
    assert not (Path(health_dir) / "dispatch").exists()
    assert not (Path(health_dir) / "retention").exists()
