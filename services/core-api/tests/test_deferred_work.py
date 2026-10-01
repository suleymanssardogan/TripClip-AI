from datetime import datetime, timedelta
from unittest import mock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.application.services.deferred_work import enqueue, dispatch_due, execute_job, MAX_ATTEMPTS
from app.models.deferred_job import DeferredJob


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _job(db):
    job = enqueue(db, "place_index", 1)
    db.commit()
    return job.id


def test_rollback_does_not_publish_work(db):
    enqueue(db, "place_index", 1)
    db.flush()
    job_id = db.query(DeferredJob.id).order_by(DeferredJob.id.desc()).first()[0]
    db.rollback()
    assert db.get(DeferredJob, job_id) is None


def test_broker_outage_is_recovered_after_dispatch_reservation(db):
    job_id = _job(db)
    now = datetime.utcnow()
    publish = mock.Mock(side_effect=RuntimeError("broker down"))
    dispatch_due(db, publish, now=now)
    assert db.get(DeferredJob, job_id).status == "queued"
    publish.reset_mock(side_effect=True)
    dispatch_due(db, publish, now=now + timedelta(seconds=61))
    assert mock.call(job_id) in publish.call_args_list


def test_duplicate_delivery_and_active_lease_are_skipped(db):
    job_id = _job(db)
    handler = mock.Mock()
    handler.side_effect = lambda *_: execute_job(db, job_id, mock.Mock(side_effect=AssertionError("duplicate")))
    assert execute_job(db, job_id, handler) == "completed"
    assert execute_job(db, job_id, handler) == "skipped"
    assert handler.call_count == 1


def test_retry_respects_backoff_then_succeeds(db):
    job_id = _job(db)
    now = datetime.utcnow()
    assert execute_job(db, job_id, mock.Mock(side_effect=RuntimeError("Qdrant down")), now=now) == "pending"
    handler = mock.Mock()
    assert execute_job(db, job_id, handler, now=now + timedelta(seconds=1)) == "skipped"
    assert execute_job(db, job_id, handler, now=now + timedelta(seconds=31)) == "completed"
    assert handler.call_count == 1
    assert db.get(DeferredJob, job_id).attempts == 2


def test_worker_loss_recovered_after_lease_expires(db):
    job_id = _job(db)
    now = datetime.utcnow()
    with pytest.raises(SystemExit):
        execute_job(db, job_id, mock.Mock(side_effect=SystemExit()), now=now)
    assert execute_job(db, job_id, mock.Mock(), now=now + timedelta(seconds=901)) == "completed"


def test_retry_limit_retains_failed_job_for_operator(db):
    job_id = _job(db)
    db.query(DeferredJob).filter_by(id=job_id).update({"attempts": MAX_ATTEMPTS - 1})
    db.commit()
    assert execute_job(db, job_id, mock.Mock(side_effect=RuntimeError("still down"))) == "failed"
    assert db.get(DeferredJob, job_id).last_error == "RuntimeError"


def test_real_index_handler_retries_false_upsert_then_completes(db):
    from tests.test_place_knowledge_retriever import _make_place
    from app.tasks.video_tasks import _run_deferred_work
    place = _make_place(db)
    job = enqueue(db, "place_index", place.id)
    db.commit()
    now = datetime.utcnow()
    with mock.patch("app.ml.qdrant_service.QdrantService") as index:
        index.return_value.upsert_place.return_value = False
        assert execute_job(db, job.id, lambda k, v: _run_deferred_work(db, k, v), now=now) == "pending"
        index.return_value.upsert_place.return_value = True
        assert execute_job(db, job.id, lambda k, v: _run_deferred_work(db, k, v),
                           now=now + timedelta(seconds=31)) == "completed"


def test_deliberately_disabled_tip_provider_does_not_retry_forever(db, monkeypatch):
    from app.tasks.video_tasks import _run_deferred_work
    from app.models.video import Video, VideoStatus
    monkeypatch.setenv("USE_GEMINI", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    video = Video(filename="test.mp4", file_path="/unused", status=VideoStatus.COMPLETED,
                  deduplicated_locations=[{"original_name": "Test place"}])
    db.add(video)
    db.commit()
    job = enqueue(db, "travel_tips", video.id)
    db.commit()
    with mock.patch("app.ml.gemini_service.GeminiService") as provider:
        assert execute_job(db, job.id, lambda k, v: _run_deferred_work(db, k, v)) == "completed"
        provider.assert_not_called()
