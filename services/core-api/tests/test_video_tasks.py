"""
video_tasks.py — yt-dlp kalıcı/geçici hata sınıflandırması testleri.
"""
from app.tasks.video_tasks import _is_permanent_yt_dlp_failure


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
