"""
TripClip AI — Celery Video İşleme Görevi.

Bu modül tek bir Celery task tanımlar: `process_video_task`.

Akış:
    FastAPI route → process_video_task.delay(video_id, video_path)
                            ↓  (Redis kuyruğuna girer)
    Celery worker → process_video_task çalışır
                            ↓
    ML pipeline → sonuçlar DB'ye kaydedilir

Retry politikası:
    - Max 3 deneme
    - Bekleme: 60s, 120s, 240s (üstel artış)
    - Başarısız olursa repo.mark_failed() çağrılır
"""
import logging
import os

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

# celery_app burada import edilir → shared_task dekoratörü hangi app'e
# bağlanacağını bilir. Bu import olmadan shared_task localhost'a düşer.
from app.core.celery_app import celery_app as _celery_app  # noqa: F401

logger = logging.getLogger("tripclip.tasks.video")


class PermanentDownloadError(Exception):
    """
    yt-dlp indirmesi, tekrar denense de asla başarılı olmayacak bir sebeple
    başarısız oldu (video silinmiş/özel/coğrafi kısıtlı/desteklenmeyen URL).
    process_url_task bu tipi autoretry_for=(Exception,) yakalamadan ÖNCE
    ayrıca yakalar ve retry etmeden hemen "failed" işaretler — aksi halde
    Instagram'ın kalıcı olarak reddettiği bir bağlantı için worker ~10 dakika
    boyunca (3 deneme, üstel backoff) anlamsız yeniden denemeler yapardı.
    """


# Instagram/yt-dlp'nin kalıcı (retry ile düzelmeyecek) hatalarda verdiği
# tipik mesaj kalıpları — küçük harfe çevrilmiş metinde aranır. Bilerek
# yalın "unavailable" gibi tek kelimeler DEĞİL, daha spesifik ifadeler
# kullanılır — aksi halde geçici "HTTP 503 Service Unavailable" gibi ağ
# hataları da (yanlışlıkla) kalıcı sayılıp retry'siz bırakılırdı.
_PERMANENT_YT_DLP_MARKERS = (
    "video unavailable",
    "not available",
    "no longer available",
    "this account is private",
    "has been removed",
    "does not exist",
    "unsupported url",
    "login required",
    "requires authentication",
    "content isn't available",
    "geo-restricted",
)


def _is_permanent_yt_dlp_failure(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _PERMANENT_YT_DLP_MARKERS)

# ── Paylaşılan VideoProcessingService instance'ı ──────────────────────────────
#
# VideoProcessingService.__init__ YOLO/BERT NER/Whisper/SentenceTransformer gibi
# ağır ML modellerini yükler (BERT NER tek başına soğuk yüklemede ~30-60s).
# Worker `--pool=solo` ile tek process olarak çalıştığı için (aynı anda tek task),
# bu servisi her task'ta yeniden oluşturmak yerine worker process başına bir kez
# oluşturup yeniden kullanıyoruz. __init__ video'ya özgü hiçbir mutable state
# tutmaz (frames_dir video_id ile parametrize edilir), bu yüzden paylaşım güvenli.
_processor = None


def _get_processor():
    global _processor
    if _processor is None:
        from app.core.services.video_processor import VideoProcessingService
        _processor = VideoProcessingService()
    return _processor


@shared_task(
    name="app.tasks.video_tasks.process_video_task",
    queue="video_processing",
    bind=True,                    # self → retry için gerekli
    max_retries=3,
    default_retry_delay=60,       # ilk retry: 60 sn sonra
    autoretry_for=(Exception,),   # tüm exception'lar için otomatik retry
    retry_backoff=True,           # 60 → 120 → 240 sn
    retry_backoff_max=300,
    retry_jitter=True,            # aynı anda gelen retry'ların dağıtılması
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_video_task(self, video_id: int, video_path: str) -> dict:
    """
    Video ML pipeline'ını Celery worker üzerinde çalıştırır.

    Args:
        video_id:   DB'deki video kaydının ID'si
        video_path: İşlenecek video dosyasının tam yolu

    Returns:
        {"status": "completed", "video_id": video_id}
    """
    from app.core.database import SessionLocal
    from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
    from app.core.redis import set_progress

    logger.info("🎬 Task başladı | video_id=%s | attempt=%s", video_id, self.request.retries + 1)

    db   = SessionLocal()
    repo = SqlVideoRepository(db)

    try:
        repo.mark_processing(video_id)
        set_progress(video_id, "queued", 2)

        processor = _get_processor()
        result    = processor.process_video(video_path, video_id)

        repo.save_results(video_id, result)
        set_progress(video_id, "completed", 100)

        logger.info("✅ Task tamamlandı | video_id=%s", video_id)
        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        logger.error("⏰ Zaman aşımı | video_id=%s", video_id)
        repo.mark_failed(video_id)
        set_progress(video_id, "failed", 0)
        raise   # Celery'nin göreceği şekilde yeniden fırlat

    except Exception as exc:
        attempt = self.request.retries + 1
        logger.error("❌ Task başarısız | video_id=%s | attempt=%s | hata: %s",
                     video_id, attempt, exc, exc_info=True)

        if self.request.retries >= self.max_retries:
            # Son deneme de başarısız → kalıcı hata
            repo.mark_failed(video_id)
            set_progress(video_id, "failed", 0)
            logger.error("💀 Kalıcı hata | video_id=%s | tüm denemeler tükendi", video_id)
        else:
            set_progress(video_id, "retrying", 0)

        raise   # autoretry_for tetiklensin

    finally:
        db.close()


# ── URL Download + Process Task ───────────────────────────────────────────────

@shared_task(
    name="app.tasks.video_tasks.process_url_task",
    queue="video_processing",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=720,
    time_limit=780,
)
def process_url_task(self, video_id: int, source_url: str, source: str = "unknown") -> dict:
    """
    Instagram URL'ini indir → ML pipeline → DB'ye kaydet.

    Args:
        video_id:   DB'deki video kaydının ID'si (önceden oluşturuldu)
        source_url: İndirilecek Instagram Reels / Post URL'i
        source:     Kaynak ("instagram_share_extension", vb.)

    Gereksinim:
        yt-dlp >= 2024.1.0  →  pip install yt-dlp
    """
    import os
    import tempfile
    from app.core.database import SessionLocal
    from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
    from app.core.redis import set_progress

    logger.info(
        "🔗 URL task başladı | video_id=%s | source=%s | url=%.60s",
        video_id, source, source_url,
    )

    db   = SessionLocal()
    repo = SqlVideoRepository(db)

    try:
        repo.mark_processing(video_id)
        set_progress(video_id, "downloading", 5)

        # ── Adım 1: URL'i indir ─────────────────────────────────────────────
        video_path = _download_url(source_url, video_id)
        set_progress(video_id, "queued", 10)

        # ── Adım 2: ML pipeline ─────────────────────────────────────────────
        processor = _get_processor()
        result    = processor.process_video(video_path, video_id)

        # ── Adım 3: Kaydet ──────────────────────────────────────────────────
        repo.save_results(video_id, result)
        set_progress(video_id, "completed", 100)

        logger.info("✅ URL task tamamlandı | video_id=%s", video_id)
        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        logger.error("⏰ URL task zaman aşımı | video_id=%s", video_id)
        repo.mark_failed(video_id)
        set_progress(video_id, "failed", 0)
        raise

    except PermanentDownloadError as exc:
        # Retry ile düzelmeyecek bir hata (video silinmiş/özel/desteklenmeyen
        # URL) — autoretry_for=(Exception,) tetiklenmeden burada hemen
        # "failed" işaretlenir ve exception YUTULUR (raise edilmez), böylece
        # Celery bunu retry etmez. ~10 dakikalık anlamsız bekleme önlenir.
        logger.error("🚫 Kalıcı indirme hatası (retry edilmeyecek) | video_id=%s | %s",
                     video_id, exc)
        repo.mark_failed(video_id)
        set_progress(video_id, "failed", 0)
        return {"status": "failed", "video_id": video_id, "reason": "permanent_download_error"}

    except Exception as exc:
        attempt = self.request.retries + 1
        logger.error(
            "❌ URL task başarısız | video_id=%s | attempt=%s | %s",
            video_id, attempt, exc, exc_info=True,
        )
        if self.request.retries >= self.max_retries:
            repo.mark_failed(video_id)
            set_progress(video_id, "failed", 0)
        else:
            set_progress(video_id, "retrying", 0)
        raise

    finally:
        db.close()


def _download_url(url: str, video_id: int) -> str:
    """
    yt-dlp ile URL'den video indir.

    Instagram için gerekli: yt-dlp >= 2024.1.0
    Kurulum: pip install yt-dlp

    Kimlik doğrulama (private Reels için):
        YT_DLP_COOKIES ortam değişkenine cookies.txt yolu verin.
    """
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp kurulu değil. `pip install yt-dlp` çalıştırın."
        ) from exc

    upload_dir  = os.getenv("UPLOAD_DIR", "/app/uploads/videos")
    os.makedirs(upload_dir, exist_ok=True)
    output_tmpl = os.path.join(upload_dir, f"url_{video_id}_%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl":        output_tmpl,
        "format":         "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "merge_output_format": "mp4",
        "quiet":          True,
        "no_warnings":    True,
        # Instagram session cookie (opsiyonel, public Reels için gerekmez)
        **({"cookiefile": os.environ["YT_DLP_COOKIES"]}
           if "YT_DLP_COOKIES" in os.environ else {}),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as exc:
        if _is_permanent_yt_dlp_failure(str(exc)):
            raise PermanentDownloadError(str(exc)) from exc
        raise   # geçici hata (ağ vb.) — autoretry_for yeniden denesin

    if not os.path.exists(filename):
        raise FileNotFoundError(f"yt-dlp indirdi ama dosya yok: {filename}")

    logger.info("📥 Video indirildi: %s (%.1f MB)",
                filename, os.path.getsize(filename) / 1_048_576)
    return filename
