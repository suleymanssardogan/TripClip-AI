from datetime import datetime, timedelta
from unittest import mock
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.video import Video, VideoStatus
from app.models.deferred_job import DeferredJob
from app.models.user import User
from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
from app.application.services.deferred_work import dispatch_due, execute_job, MAX_ATTEMPTS


@pytest.fixture
def factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id=1, username="owner", email="owner@example.com")); db.commit()
    yield factory
    engine.dispose()


def test_video_and_analysis_request_commit_together(factory):
    with factory() as db:
        video = SqlVideoRepository(db).create("test.mp4", "/tmp/test.mp4", 1)
        job = db.query(DeferredJob).one()
        assert (job.kind, job.entity_id, job.status) == ("video_analysis", video.id, "pending")
    with factory() as db:
        assert db.query(Video).count() == db.query(DeferredJob).count() == 1


def test_outbox_failure_rolls_back_video(factory):
    with factory() as db:
        with mock.patch("app.application.services.deferred_work.enqueue", side_effect=RuntimeError("outbox failed")):
            with pytest.raises(RuntimeError):
                SqlVideoRepository(db).create("test.mp4", "/tmp/test.mp4", 1)
        assert db.query(Video).count() == db.query(DeferredJob).count() == 0


def test_url_survives_broker_outage_and_can_be_republished(factory):
    with factory() as db:
        video = SqlVideoRepository(db).create("url.mp4", "/tmp/placeholder", 1,
                                               source_url="https://www.instagram.com/reel/test/", source_platform="ios")
        job = db.query(DeferredJob).one(); now = datetime.utcnow()
        publish = mock.Mock(side_effect=RuntimeError("broker offline"))
        assert dispatch_due(db, publish, now=now) == 0
        assert db.get(Video, video.id).source_url.endswith("/test/")
        publish.side_effect = None
        assert dispatch_due(db, publish, now=now + timedelta(seconds=61)) == 1
        publish.assert_called_with(job.id)


@pytest.mark.parametrize("url", [None, "https://www.instagram.com/reel/test/"])
def test_main_worker_selects_persisted_input_and_skips_redelivery(factory, url):
    from app.tasks import video_tasks
    with factory() as db:
        video = SqlVideoRepository(db).create("test.mp4", "/tmp/test.mp4", 1, source_url=url, source_platform="ios")
        vid = video.id; job_id = db.query(DeferredJob).one().id
    def complete(context, video_id, *args):
        with factory() as db:
            video = db.get(Video, video_id); video.status = VideoStatus.COMPLETED; db.commit()
    with mock.patch("app.core.database.SessionLocal", factory), \
         mock.patch.object(video_tasks, "_process_uploaded_analysis", side_effect=complete) as upload, \
         mock.patch.object(video_tasks, "_process_url_analysis", side_effect=complete) as download:
        assert video_tasks.durable_analysis_task.run(job_id) == "completed"
        assert video_tasks.durable_analysis_task.run(job_id) == "skipped"
        selected = download if url else upload
        assert selected.call_count == 1
        assert selected.call_args.args[2] == (url or "/tmp/test.mp4")


def test_final_worker_loss_marks_video_failed(factory):
    with factory() as db:
        video = SqlVideoRepository(db).create("test.mp4", "/tmp/test.mp4", 1)
        job = db.query(DeferredJob).one()
        video.status = VideoStatus.PROCESSING
        job.status = "processing"; job.attempts = MAX_ATTEMPTS
        job.lease_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        dispatch_due(db, mock.Mock())
        db.expire_all()
        assert video.status == VideoStatus.FAILED and job.status == "failed"


def test_transient_failure_is_pending_not_terminal_and_backoff_applies(factory):
    with factory() as db:
        video = SqlVideoRepository(db).create("test.mp4", "/tmp/test.mp4", 1)
        job = db.query(DeferredJob).one(); now = datetime.utcnow()
        assert execute_job(db, job.id, mock.Mock(side_effect=RuntimeError), now=now) == "pending"
        db.expire_all()
        assert video.status == VideoStatus.UPLOADED
        assert execute_job(db, job.id, mock.Mock(), now=now + timedelta(seconds=1)) == "skipped"
        assert execute_job(db, job.id, mock.Mock(), now=now + timedelta(seconds=31)) == "completed"


def test_url_schema_migration_roundtrip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'main-analysis.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url); Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE videos DROP COLUMN source_platform"))
        connection.execute(text("ALTER TABLE videos DROP COLUMN source_url"))
    cfg = Config("alembic.ini"); cfg.set_main_option("sqlalchemy.url", url)
    command.stamp(cfg, "f7c21a904d63"); command.upgrade(cfg, "head")
    assert {"source_url", "source_platform"} <= {c["name"] for c in inspect(engine).get_columns("videos")}
    command.downgrade(cfg, "f7c21a904d63")
    assert "source_url" not in {c["name"] for c in inspect(engine).get_columns("videos")}
    engine.dispose()


def test_upload_accepted_during_broker_outage(client, bff_headers, monkeypatch):
    import app.api.internal.videos as routes
    monkeypatch.setattr(routes, "_enforce_daily_quota", lambda _: None)
    with mock.patch("app.application.services.deferred_work.dispatch_pending_work", side_effect=RuntimeError("offline")):
        response = client.post("/internal/videos/process", files={"file": ("test.mp4", b"video", "video/mp4")}, headers=bff_headers)
    assert response.status_code == 200
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        vid = response.json()["id"]
        assert db.get(Video, vid) is not None
        assert db.query(DeferredJob).filter_by(kind="video_analysis", entity_id=vid).one().status == "pending"


def test_terminal_sql_status_overrides_old_redis_progress():
    from app.application.services.video_service import VideoService
    repo = mock.Mock()
    repo.get_by_id.return_value = Video(id=1, filename="test.mp4", file_path="", status=VideoStatus.FAILED,
                                       created_at=datetime.utcnow())
    redis = mock.Mock(); redis.get.return_value = '{"stage":"processing","percent":30}'
    result = VideoService(repo, analytics=mock.Mock()).get_progress(1, redis)
    assert result.stage == "failed" and result.percent == 0
    redis.get.assert_not_called()
