"""
video_tasks.py — yt-dlp kalıcı/geçici hata sınıflandırması ve
shared_trip_created analytics kaydı testleri.
"""
from unittest import mock
from types import SimpleNamespace
import pytest

from app.tasks.video_tasks import _is_permanent_yt_dlp_failure, _track_trip_created


@pytest.mark.parametrize("from_url", [False, True])
def test_completed_analysis_survives_tips_broker_failure(tmp_path, from_url):
    from app.tasks import video_tasks

    path = tmp_path / "video.mp4"
    path.write_bytes(b"test-video")
    processor = mock.MagicMock()
    processor.process_video.return_value = {"deduplicated_locations": []}
    repo = mock.MagicMock()
    db = mock.MagicMock()
    with mock.patch("app.core.database.SessionLocal", return_value=db), \
         mock.patch("app.infrastructure.repositories.sql_video_repository.SqlVideoRepository", return_value=repo), \
         mock.patch("app.core.redis.set_progress"), \
         mock.patch.object(video_tasks, "_get_processor", return_value=processor), \
         mock.patch.object(video_tasks, "_notify_push"), \
         mock.patch.object(video_tasks, "_track_trip_created"), \
         mock.patch.object(video_tasks, "_download_url", return_value=str(path)), \
         mock.patch("app.application.services.deferred_work.dispatch_pending_work", side_effect=RuntimeError("broker down")):
        if from_url:
            result = video_tasks.process_url_task.run(42, "https://example.test/video")
        else:
            result = video_tasks.process_video_task.run(42, str(path))

    assert result == {"status": "completed", "video_id": 42}
    processor.process_video.assert_called_once_with(str(path), 42, defer_tips=True)
    repo.save_results.assert_called_once()
    repo.mark_failed.assert_not_called()
    db.close.assert_called_once()
    # Uploads survive retries and remain owned by upload storage. URL
    # downloads are task-local temporary files, removed after processing.
    assert path.exists() is (not from_url)


def test_url_download_failure_does_not_mask_original_exception():
    from app.tasks import video_tasks

    repo = mock.MagicMock()
    with mock.patch("app.core.database.SessionLocal"), \
         mock.patch("app.infrastructure.repositories.sql_video_repository.SqlVideoRepository", return_value=repo), \
         mock.patch("app.core.redis.set_progress"), \
         mock.patch.object(video_tasks, "_notify_push"), \
         mock.patch.object(video_tasks, "_download_url", side_effect=video_tasks.PermanentDownloadError("private")):
        result = video_tasks.process_url_task.run(42, "https://example.test/video")
    assert result["reason"] == "permanent_download_error"
    repo.mark_failed.assert_called_once_with(42)


@pytest.mark.parametrize("from_url", [False, True])
@pytest.mark.parametrize("status", ["completed", None])
def test_redelivery_or_deleted_video_never_runs_ai(from_url, status):
    from app.tasks import video_tasks

    repo = mock.MagicMock()
    repo.get_by_id.return_value = SimpleNamespace(status=status) if status else None
    with mock.patch("app.core.database.SessionLocal"), \
         mock.patch("app.infrastructure.repositories.sql_video_repository.SqlVideoRepository", return_value=repo), \
         mock.patch.object(video_tasks, "_get_processor") as processor, \
         mock.patch.object(video_tasks, "_download_url") as download:
        task = video_tasks.process_url_task if from_url else video_tasks.process_video_task
        result = task.run(42, "input")
    assert result["status"] == ("completed" if status else "skipped")
    processor.assert_not_called()
    download.assert_not_called()
    repo.mark_processing.assert_not_called()


def test_permanent_failure_markers_detected():
    permanent_messages = [
        "ERROR: [Instagram] This video unavailable",
        "This account is private",
        "Requested content is not available, try with a different account",
        "Unsupported URL: https://example.com/foo",
        "Login required to view this content",
    ]
    for msg in permanent_messages:
        assert _is_permanent_yt_dlp_failure(msg), f"beklenen kalıcı hata: {msg}"


def test_transient_failure_not_flagged_as_permanent():
    """Geçici ağ hataları (503 Service Unavailable, timeout, connection reset)
    retry edilebilmeli — yanlışlıkla kalıcı sayılmamalı."""
    transient_messages = [
        "Connection reset by peer",
        "HTTP Error 503: Service Unavailable",
        "urlopen error timed out",
        "",
    ]
    for msg in transient_messages:
        assert not _is_permanent_yt_dlp_failure(msg), f"beklenen geçici hata: {msg}"


# ─── _track_trip_created ──────────────────────────────────────────────────────

def test_track_trip_created_records_shared_trip_created_event():
    fake_video = mock.MagicMock(id=42, user_id=7)
    fake_repo = mock.MagicMock()
    fake_repo.get_by_id.return_value = fake_video
    fake_analytics = mock.MagicMock()

    with mock.patch(
        "app.infrastructure.repositories.sql_video_repository.SqlVideoRepository",
        return_value=fake_repo,
    ), mock.patch(
        "app.application.services.analytics_service.get_analytics_service",
        return_value=fake_analytics,
    ):
        _track_trip_created(db=mock.MagicMock(), video_id=42)

    fake_analytics.track.assert_called_once()
    _, kwargs = fake_analytics.track.call_args
    assert kwargs["trip_id"] == 42
    assert kwargs["user_id"] == 7
    assert kwargs["platform"] == "server"
    assert kwargs["event"].value == "shared_trip_created"


def test_track_trip_created_skips_when_video_not_found():
    fake_repo = mock.MagicMock()
    fake_repo.get_by_id.return_value = None
    fake_analytics = mock.MagicMock()

    with mock.patch(
        "app.infrastructure.repositories.sql_video_repository.SqlVideoRepository",
        return_value=fake_repo,
    ), mock.patch(
        "app.application.services.analytics_service.get_analytics_service",
        return_value=fake_analytics,
    ):
        _track_trip_created(db=mock.MagicMock(), video_id=999)

    fake_analytics.track.assert_not_called()


def test_track_trip_created_never_raises_on_db_error():
    """Best-effort: video_tasks'ın kritik yolunu (pipeline sonucu) hiçbir zaman etkilememeli."""
    with mock.patch(
        "app.infrastructure.repositories.sql_video_repository.SqlVideoRepository",
        side_effect=RuntimeError("db connection lost"),
    ):
        _track_trip_created(db=mock.MagicMock(), video_id=1)  # exception fırlatmamalı
