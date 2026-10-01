import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.core.privacy import DataTransferBlocked, require_reviewed_transfer, scrub_error_event
from app.models.video import Video, VideoStatus
from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository


def test_production_transfer_denied_without_specific_review(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRIVACY_REVIEWED_PROVIDERS", "ollama")
    with pytest.raises(DataTransferBlocked):
        require_reviewed_transfer("gemini")
    require_reviewed_transfer("ollama")


def test_development_not_blocked(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    require_reviewed_transfer("gemini")


def test_scrub_removes_request_identity_and_exception_locals():
    event = {"user": {"email": "private@example.com"}, "request": {"data": "secret"},
             "breadcrumbs": [{"message": "secret"}], "extra": {"prompt": "secret"},
             "logentry": {"formatted": "secret"}, "exception": {"values": [
                 {"type": "ValueError", "value": "secret", "stacktrace": {"frames": [
                     {"filename": "app.py", "vars": {"token": "secret"}}]}}]}}
    result = scrub_error_event(event, {})
    assert "secret" not in str(result)
    assert "ValueError" in str(result)


def test_private_videos_never_appear_in_public_feed_including_city_filter():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        private = Video(filename="personal.mp4", file_path="/tmp/private", status=VideoStatus.COMPLETED,
                        deduplicated_locations=[{"original_name": "Istanbul"}], extracted_texts=["private OCR"])
        public = Video(filename="sensitive-original.mp4", file_path="/tmp/public", status=VideoStatus.COMPLETED,
                       is_public=True, deduplicated_locations=[{"original_name": "Istanbul"}], extracted_texts=["private OCR"])
        db.add_all([private, public]); db.commit()
        assert private.is_public is False
        repo = SqlVideoRepository(db)
        for city in (None, "Istanbul"):
            feed = repo.get_completed(city=city)
            assert feed["total"] == 1
            assert feed["plans"][0]["id"] == public.id
            assert feed["plans"][0]["filename"] == "Gezi planı"
            assert feed["plans"][0]["ocr_preview"] == []
    engine.dispose()


def test_retention_removes_only_expired_finished_files(tmp_path):
    from datetime import datetime, timedelta
    from app.application.services.privacy_retention import purge_expired_uploads
    from app.models.privacy_erasure_record import PrivacyErasureRecord
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    root = tmp_path / "uploads"; root.mkdir()
    now = datetime(2026, 10, 1)
    with Session(engine) as db:
        for name, status, hours in [("old.mp4", VideoStatus.COMPLETED, 25), ("active.mp4", VideoStatus.PROCESSING, 200), ("new.mp4", VideoStatus.COMPLETED, 1), ("failed.mp4", VideoStatus.FAILED, 169)]:
            path = root / name; path.write_bytes(b"video")
            db.add(Video(filename=name, file_path=str(path), status=status, created_at=now-timedelta(hours=hours)))
        outside = tmp_path / "outside.mp4"; outside.write_bytes(b"private")
        db.add(Video(filename="outside.mp4", file_path=str(outside), status=VideoStatus.COMPLETED, created_at=now-timedelta(days=4)))
        db.commit()
        assert purge_expired_uploads(db, root, now) == 2
        assert outside.exists() and (root / "active.mp4").exists() and (root / "new.mp4").exists()
        assert not (root / "old.mp4").exists() and not (root / "failed.mp4").exists()
        assert db.query(PrivacyErasureRecord).one().count == 2
        assert purge_expired_uploads(db, root, now) == 0
        assert db.query(PrivacyErasureRecord).count() == 1
    engine.dispose()


def test_private_completed_detail_rejected_for_nonowner():
    from unittest.mock import Mock
    from datetime import datetime
    from fastapi import HTTPException
    from app.application.services.video_service import VideoService
    repo = Mock()
    repo.get_by_id.return_value = Video(id=1, user_id=7, filename="private.mp4", file_path="", status=VideoStatus.COMPLETED, is_public=False, created_at=datetime.utcnow())
    service = VideoService(repo, analytics=Mock())
    for requester in (None, 8):
        with pytest.raises(HTTPException) as exc:
            service.get_video_detail(1, requesting_user_id=requester)
        assert exc.value.status_code == 404
    assert service.get_video_detail(1, requesting_user_id=7).filename == "private.mp4"


def test_public_detail_redacts_raw_content():
    from unittest.mock import Mock
    from datetime import datetime
    from app.application.services.video_service import VideoService
    repo = Mock()
    repo.get_by_id.return_value = Video(id=1, user_id=7, filename="secret.mp4", file_path="", status=VideoStatus.COMPLETED, is_public=True, created_at=datetime.utcnow(), transcription={"text": "secret"}, extracted_texts=["secret"], ocr_pois=["secret"])
    result = VideoService(repo, analytics=Mock()).get_video_detail(1, requesting_user_id=8)
    assert "secret" not in str(result.model_dump())


def test_postgres_claim_uses_transaction_lock_and_releases_on_exception():
    from unittest.mock import MagicMock
    from app.core.video_claim import analysis_claim
    engine = MagicMock(); engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar.return_value = True
    with pytest.raises(ValueError):
        with analysis_claim(42, engine) as acquired:
            assert acquired
            raise ValueError("worker failure")
    assert "pg_try_advisory_xact_lock" in str(connection.execute.call_args.args[0])
    connection.begin.return_value.__exit__.assert_called_once()


def test_pending_file_erasure_survives_database_record_deletion(tmp_path):
    from datetime import datetime
    from app.models.privacy_erasure_record import PendingFileErasure
    from app.application.services.privacy_retention import purge_expired_uploads
    engine = create_engine("sqlite://"); Base.metadata.create_all(engine)
    path = tmp_path / "deleted-account.mp4"; path.write_bytes(b"personal")
    with Session(engine) as db:
        db.add(PendingFileErasure(file_path=str(path))); db.commit()
        assert purge_expired_uploads(db, tmp_path, datetime(2026, 10, 1)) == 1
        assert not path.exists()
        assert db.query(PendingFileErasure).count() == 0
    engine.dispose()


def test_privacy_migration_roundtrip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text
    url = f"sqlite:///{tmp_path / 'privacy-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    excluded = {"privacy_erasure_records", "pending_file_erasures"}
    Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n not in excluded])
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE videos DROP COLUMN is_public"))
        connection.execute(text("INSERT INTO videos (filename, file_path, status) VALUES ('old.mp4', '/tmp/old', 'COMPLETED')"))
    cfg = Config("alembic.ini"); cfg.set_main_option("sqlalchemy.url", url)
    command.stamp(cfg, "e6b9d18a40c2"); command.upgrade(cfg, "f7c21a904d63")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT is_public FROM videos")).scalar() == 0
    assert excluded <= set(inspect(engine).get_table_names())
    command.downgrade(cfg, "e6b9d18a40c2")
    assert not excluded.intersection(inspect(engine).get_table_names())
    assert "is_public" not in {c["name"] for c in inspect(engine).get_columns("videos")}
    engine.dispose()


def test_gemini_blocked_before_network(monkeypatch):
    from unittest.mock import Mock
    from app.ml.gemini_service import GeminiService
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRIVACY_REVIEWED_PROVIDERS", "")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    post = Mock(); monkeypatch.setattr("app.ml.gemini_service._requests.post", post)
    with pytest.raises(DataTransferBlocked):
        GeminiService()._call([{"text": "private"}])
    post.assert_not_called()


def test_ollama_blocked_before_network(monkeypatch):
    from unittest.mock import Mock
    from app.ml.rag_service import RAGService
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRIVACY_REVIEWED_PROVIDERS", "")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    post = Mock(); monkeypatch.setattr("app.ml.rag_service.requests.post", post)
    service = RAGService()
    with pytest.raises(DataTransferBlocked):
        service._generate("private")
    with pytest.raises(DataTransferBlocked):
        service.answer_question("system", "private")
    post.assert_not_called()


def test_account_delete_commits_file_erasure_and_retries_permission_error(tmp_path):
    from unittest.mock import patch
    from datetime import datetime
    from app.models.user import User
    from app.models.privacy_erasure_record import PendingFileErasure, PrivacyErasureRecord
    from app.infrastructure.repositories.sql_user_repository import SqlUserRepository
    from app.application.services.privacy_retention import purge_expired_uploads
    engine = create_engine("sqlite://"); Base.metadata.create_all(engine)
    path = tmp_path / "account.mp4"; path.write_bytes(b"private")
    with Session(engine) as db:
        user = User(email="delete@example.com", username="delete_me"); db.add(user); db.flush()
        uid = user.id
        db.add(Video(user_id=uid, filename="account.mp4", file_path=str(path))); db.commit()
        assert SqlUserRepository(db).delete_account(uid) == [str(path)]
        assert db.query(User).count() == 0 and db.query(Video).count() == 0
        assert db.query(PendingFileErasure).count() == 1
        assert db.query(PrivacyErasureRecord).one().category == "account_sql_records"
        with patch("pathlib.Path.unlink", side_effect=PermissionError):
            assert purge_expired_uploads(db, tmp_path, datetime(2026, 10, 1)) == 0
        assert db.query(PendingFileErasure).count() == 1 and path.exists()
        assert purge_expired_uploads(db, tmp_path, datetime(2026, 10, 1)) == 1
        assert db.query(PendingFileErasure).count() == 0 and not path.exists()
    engine.dispose()
