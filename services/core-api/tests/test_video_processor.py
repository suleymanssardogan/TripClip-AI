"""
VideoProcessingService — graceful degradation testleri.

Gerçek ML kütüphanelerini (YOLO ağırlığı indirme, Whisper/BERT model yükleme)
tetiklemeden, pipeline'ın hata izolasyon mekanizmalarını (_safe_run, _try_init,
tek servis init hatasının diğerlerini etkilememesi) doğrular.
"""
import threading
import time
from concurrent.futures import Future
from unittest import mock

import pytest

from app.core.services.video_processor import (
    VideoProcessingService,
    _safe_run,
    _FFmpegTimeout,
    _FFmpegTimeoutGuard,
)


# ─── _safe_run ────────────────────────────────────────────────────────────────

def test_safe_run_returns_success_result_for_fn():
    result = _safe_run("Test", lambda: 42, fallback=0)
    assert result.success is True
    assert result.fallback_used is False
    assert result.data == 42


def test_safe_run_falls_back_on_exception():
    def boom():
        raise ValueError("bad input")

    result = _safe_run("Test", boom, fallback="default")
    assert result.success is False
    assert result.fallback_used is True
    assert result.data == "default"
    assert "bad input" in result.error


def test_safe_run_falls_back_on_future_timeout():
    never_resolved = Future()  # gerçek thread'e ihtiyaç yok — sadece timeout davranışı test ediliyor
    result = _safe_run("Test", None, fallback="fb", future=never_resolved, timeout=0.05)
    assert result.fallback_used is True
    assert result.data == "fb"
    assert "timeout" in result.error


# ─── _try_init ──────────────────────────────────────────────────────────────

def test_try_init_returns_instance_on_success():
    assert VideoProcessingService._try_init("Test", lambda: "ok") == "ok"


def test_try_init_returns_none_on_failure_instead_of_raising():
    def boom():
        raise RuntimeError("model ağırlığı indirilemedi")

    assert VideoProcessingService._try_init("Test", boom) is None


# ─── __init__ — tek servisin başlatma hatası diğerlerini etkilememeli ────────

def test_init_isolates_single_service_failure():
    """
    YOLO init'i (ağ hatası, model indirilemedi vb.) başarısız olsa bile diğer
    servisler kurulmaya devam etmeli ve _ml_available True kalmalı — eskiden
    tüm __init__ tek bir try/except ImportError içindeydi ve bu senaryoda
    VideoProcessingService'in kendisi hiç oluşturulamıyordu (bkz. video_processor.py
    _try_init yorumu).
    """
    with mock.patch("pathlib.Path.mkdir"), \
         mock.patch("app.ml.computer_vision.ObjectDetectionService", side_effect=RuntimeError("yolo indirilemedi")), \
         mock.patch("app.ml.computer_vision.LandmarkDetectionService") as m_vision, \
         mock.patch("app.ml.ocr_service.OCRService") as m_ocr, \
         mock.patch("app.ml.speech_to_text.AudioProcessingService") as m_audio, \
         mock.patch("app.ml.ner_service.NERService") as m_ner, \
         mock.patch("app.ml.places_service.PlacesService") as m_places, \
         mock.patch("app.ml.route_optimizer.RouteOptimizer") as m_route, \
         mock.patch("app.ml.rag_service.RAGService") as m_rag:
        service = VideoProcessingService()

    assert service._ml_available is True
    assert service.detector is None            # başarısız olan servis
    assert service.vision_detector is m_vision.return_value
    assert service.ocr is m_ocr.return_value
    assert service.audio_processor is m_audio.return_value
    assert service.ner is m_ner.return_value
    assert service.places is m_places.return_value
    assert service.route_optimizer is m_route.return_value
    assert service.rag is m_rag.return_value


def test_init_sets_ml_unavailable_on_import_error():
    """ffmpeg gibi temel bir bağımlılık hiç kurulu değilse (test ortamı),
    pipeline'ın tamamı kullanılamaz olarak işaretlenmeli — bu ayrım hâlâ korunmalı."""
    with mock.patch("pathlib.Path.mkdir"), \
         mock.patch.dict("sys.modules", {"ffmpeg": None}):
        service = VideoProcessingService()

    assert service._ml_available is False


# ─── _FFmpegTimeoutGuard (M39 audit bulgusu) ─────────────────────────────────
#
# `--pool=solo` Celery'nin kendi task_soft_time_limit/task_time_limit'ini
# uygulamıyor; ffmpeg-python'ın kendisi de subprocess çağrılarına bir
# timeout parametresi sunmuyor. Bu testler, o boşluğu kapatan SIGALRM
# tabanlı korumanın kendisini (gerçek ffmpeg'e hiç dokunmadan) doğrular.

def test_ffmpeg_timeout_guard_raises_when_work_exceeds_timeout():
    with pytest.raises(_FFmpegTimeout):
        with _FFmpegTimeoutGuard(1, "test"):
            time.sleep(2)


def test_ffmpeg_timeout_guard_does_not_raise_when_work_finishes_in_time():
    with _FFmpegTimeoutGuard(5, "test"):
        time.sleep(0)  # anında biter — alarm hiç tetiklenmemeli


def test_ffmpeg_timeout_guard_is_a_noop_off_the_main_thread():
    """Sinyal işleyicileri yalnızca ANA thread'de kurulabilir — ana thread
    dışında bu koruma sessizce devre dışı kalmalı (hata FIRLATMAMALI),
    eski (korumasız) davranışa düşülür. Bu, koruma eklenmeden önce zaten var
    olan davranıştır — regresyon değil, bilinçli bir sınır."""
    result: dict = {}

    def _worker():
        try:
            with _FFmpegTimeoutGuard(1, "test"):
                time.sleep(0)
            result["ok"] = True
        except Exception as exc:  # pragma: no cover - başarısız olursa teşhis için
            result["error"] = exc

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=5)

    assert result.get("ok") is True
    assert "error" not in result
