"""
video_tasks.py — yt-dlp kalıcı/geçici hata sınıflandırması ve
shared_trip_created analytics kaydı testleri.
"""
from unittest import mock

from app.tasks.video_tasks import _is_permanent_yt_dlp_failure, _track_trip_created


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
