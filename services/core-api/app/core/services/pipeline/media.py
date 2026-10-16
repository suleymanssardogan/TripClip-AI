"""Media preparation: bounded FFmpeg probing, frames and thumbnail."""
import logging
import signal
import threading
from pathlib import Path
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

# ffmpeg.probe()/ffmpeg-python'ın .run() metotları subprocess'e bir timeout
# PARAMETRESİ geçirmiyor — `--pool=solo` (bkz. CLAUDE.md worker komutu)
# Celery'nin kendi `task_soft_time_limit`/`task_time_limit`'ini de
# UYGULAMIYOR (tek process, sinyalle durdurulacak ayrı bir alt process yok).
# Sonuç: bozuk/kesik bir video dosyası ffmpeg'i sonsuza dek asabiliyor ve
# `--pool=solo` tek seferde tek görev işlediği için bu, TEK bir kötü video
# için TÜM kullanıcıların işlem kuyruğunu kalıcı olarak kilitliyordu (M39
# audit bulgusu). `_FFmpegTimeoutGuard` bu iki çağrıyı `SIGALRM` ile sınırlar.
_FFMPEG_PROBE_TIMEOUT_SECONDS = 30
_FFMPEG_EXTRACT_TIMEOUT_SECONDS = 180


class _FFmpegTimeout(Exception):
    """`_get_metadata`/`_extract_frames`'in ffmpeg subprocess çağrıları
    zaman aşımına uğradığında fırlatılır."""


class _FFmpegTimeoutGuard:
    """`SIGALRM` tabanlı zaman aşımı — yalnızca ANA thread'de devreye girer
    (bu metotların GERÇEKTE çağrıldığı yer, paralel AI aşamaları
    BAŞLAMADAN önce; sinyal işleyicileri yalnızca ana thread'de kurulabilir).
    Ana thread değilse sessizce hiçbir şey yapmaz — bu durumda ESKİ
    (korumasız) davranışa düşülür, hata FIRLATILMAZ; bu koruma yalnızca
    ek bir güvenlik ağıdır, davranış değişikliği için gereken bir ön koşul
    DEĞİLDİR."""

    def __init__(self, seconds: int, label: str):
        self._seconds = seconds
        self._label = label
        self._active = threading.current_thread() is threading.main_thread()
        self._previous_handler = None

    def __enter__(self):
        if not self._active:
            return self

        def _on_alarm(signum, frame):
            raise _FFmpegTimeout(f"{self._label} {self._seconds}s içinde tamamlanmadı")

        self._previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(self._seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._active:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._previous_handler)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ServiceResult — Her AI servisinin çıktısını taşır
# ─────────────────────────────────────────────────────────────────────────────

class MediaStages:
    def _get_metadata(self, video_path: str) -> Dict:
        import ffmpeg
        try:
            with _FFmpegTimeoutGuard(_FFMPEG_PROBE_TIMEOUT_SECONDS, "ffmpeg.probe"):
                probe = ffmpeg.probe(video_path)
            video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
            fps_str      = video_stream.get("r_frame_rate", "30/1")
            num, den     = fps_str.split("/")
            return {
                "duration": float(probe["format"]["duration"]),
                "width":    int(video_stream["width"]),
                "height":   int(video_stream["height"]),
                "fps":      round(float(num) / float(den), 2),
            }
        except Exception as e:
            logger.error("Metadata çıkarma başarısız: %s", e)
            raise

    def _extract_frames(self, video_path: str, output_dir: Path, fps: float = 0.5) -> List[str]:
        import ffmpeg
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with _FFmpegTimeoutGuard(_FFMPEG_EXTRACT_TIMEOUT_SECONDS, "ffmpeg frame extraction"):
                (
                    ffmpeg.input(video_path)
                    .filter("fps", fps=fps)
                    .output(str(output_dir / "frame_%04d.jpg"), quality=2)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            frames = sorted(output_dir.glob("*.jpg"))
            return [str(f) for f in frames if f.name.startswith("frame_")]
        except ffmpeg.Error as e:
            logger.error("FFmpeg hatası: %s", e.stderr.decode())
            raise

    def _create_thumbnail(self, first_frame: Optional[str]) -> Optional[str]:
        if not first_frame:
            return None
        import ffmpeg
        try:
            thumb_path = Path(first_frame).parent / "thumbnail.jpg"
            (
                ffmpeg.input(first_frame)
                .filter("scale", 320, -1)
                .output(str(thumb_path))
                .overwrite_output()
                .run(quiet=True)
            )
            return str(thumb_path)
        except Exception as e:
            logger.error("Thumbnail oluşturulamadı: %s", e)
            return None
