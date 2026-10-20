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

from celery.exceptions import SoftTimeLimitExceeded
from app.core.video_claim import serialized_analysis

# @_celery_app.task (shared_task DEĞİL) kasıtlı: shared_task, task.app'i
# celery.current_app (thread-local) proxy'si üzerinden çözer. FastAPI'nin sync
# route handler'ları (bu task'ları .delay() ile çağıran /process, /queue-url)
# Starlette tarafından bir threadpool worker thread'inde çalıştırılır — o
# thread'in current_app'i ana thread'deki ile AYNI DEĞİLDİR, boş bir thread-local
# stack'e düşer ve celery sıfır konfigürasyonlu (broker=None) bir varsayılan
# Celery() app'i icat eder. Sonuç: .delay() sessizce AMQP/localhost'a bağlanmaya
# çalışıp ConnectionRefusedError ile patlar, çağıran taraftaki geniş except
# bloğu bunu yutar — video "kuyruğa alındı" der ama asla işlenmez.
# @_celery_app.task, task.app'i current_app'ten BAĞIMSIZ olarak kalıcı şekilde
# bu app'e bağlar; hangi thread'den çağrılırsa çağrılsın doğru broker kullanılır.
from app.core.celery_app import celery_app as _celery_app

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


def _notify_push(db, video_id: int, completed: bool) -> None:
    """
    Video tamamlandığında/kalıcı olarak başarısız olduğunda kullanıcıya APNs
    push bildirimi gönderir. Best-effort: APNs yapılandırılmamışsa veya istek
    başarısız olursa pipeline sonucunu ETKİLEMEZ — Place senkronizasyonundaki
    (sql_video_repository.save_results) aynı fail-open deseni.
    """
    try:
        from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
        from app.infrastructure.repositories.sql_user_repository import SqlUserRepository
        from app.application.services.push_service import PushService

        video = SqlVideoRepository(db).get_by_id(video_id)
        if video is None:
            return

        service = PushService(SqlUserRepository(db))
        if completed:
            service.notify_video_completed(video)
        else:
            service.notify_video_failed(video)
    except Exception:
        logger.exception("📵 Push bildirimi başarısız (best-effort) | video_id=%s", video_id)


def _track_trip_created(db, video_id: int) -> None:
    """
    Video COMPLETED olduğunda `shared_trip_created` event'ini kaydeder — bu,
    videonun paylaşım sayfasının (web `/share/[id]`) erişilebilir hale geldiği
    andır (bkz. docs/analytics/shared-trip-events.md). Best-effort: analytics
    yazımı başarısız olsa bile pipeline sonucunu ETKİLEMEZ, aynı fail-open
    deseni _notify_push ile paylaşılıyor.
    """
    try:
        from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
        from app.application.services.analytics_service import get_analytics_service
        from app.core.analytics_events import AnalyticsEvent

        video = SqlVideoRepository(db).get_by_id(video_id)
        if video is None:
            return

        get_analytics_service().track(
            event=AnalyticsEvent.SHARED_TRIP_CREATED,
            trip_id=video_id,
            platform="server",
            user_id=video.user_id,
            source="pipeline_completed",
        )
    except Exception:
        logger.exception("📊 Analytics kaydı başarısız (best-effort) | video_id=%s", video_id)

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


@_celery_app.task(
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
    soft_time_limit=720,
    time_limit=780,
)
def process_video_task(self, video_id: int, video_path: str) -> dict:
    return _process_uploaded_analysis(self, video_id, video_path)


@serialized_analysis
def _process_uploaded_analysis(self, video_id: int, video_path: str) -> dict:
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
        existing_result = _existing_analysis_result(repo, video_id)
        if existing_result is not None:
            return existing_result
        repo.mark_processing(video_id)
        set_progress(video_id, "queued", 2)

        processor = _get_processor()
        # İpuçları kritik yolda değil — kullanıcı haritayı ve mekanları
        # görmek için beklemesin. Video COMPLETED işaretlendikten sonra
        # ayrı task üretiyor (ölçüm: ~6s kazanç).
        result    = processor.process_video(video_path, video_id, defer_tips=True)

        repo.save_results(video_id, result)
        set_progress(video_id, "completed", 100)

        logger.info("✅ Task tamamlandı | video_id=%s", video_id)
        _notify_push(db, video_id, completed=True)
        _track_trip_created(db, video_id)

        # Sonucu kaydettikten SONRA kuyruğa al — bu task başarısız olsa bile
        # video COMPLETED kalır, sadece ipuçları eksik olur.

        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        if getattr(self, "durable", False):
            raise
        logger.error("⏰ Zaman aşımı | video_id=%s", video_id)
        repo.mark_failed(video_id)
        set_progress(video_id, "failed", 0)
        _notify_push(db, video_id, completed=False)
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
            _notify_push(db, video_id, completed=False)
        else:
            set_progress(video_id, "retrying", 0)

        raise   # autoretry_for tetiklensin

    finally:
        db.close()


def _existing_analysis_result(repo, video_id: int):
    """Celery can redeliver acknowledged-late tasks; avoid duplicate AI work."""
    video = repo.get_by_id(video_id)
    if video is None:
        return {"status": "skipped", "video_id": video_id, "reason": "video_deleted"}
    if video.status == "completed":
        return {"status": "completed", "video_id": video_id}
    return None


@_celery_app.task(name="app.tasks.video_tasks.deferred_work_task", queue="video_processing",
                  acks_late=True, reject_on_worker_lost=True,
                  soft_time_limit=210, time_limit=240)
def deferred_work_task(job_id: int):
    from app.core.database import SessionLocal
    from app.application.services.deferred_work import execute_job
    with SessionLocal() as db:
        return execute_job(db, job_id, lambda kind, entity_id: _run_deferred_work(db, kind, entity_id))


def _run_deferred_work(db, kind, entity_id):
    if kind == "library_sync":
        from app.models.video import Video
        from app.infrastructure.repositories.sql_place_repository import SqlPlaceRepository
        video = db.get(Video, entity_id)
        if video is not None and video.status == "completed":
            SqlPlaceRepository(db).sync_from_video(video)
    elif kind == "place_index":
        from datetime import datetime
        from app.models.place import Place
        from app.models.place_knowledge_document import PlaceKnowledgeDocument
        from app.ml.qdrant_service import QdrantService
        place = db.query(Place).filter_by(id=entity_id).first()
        if place is None:
            return
        docs = db.query(PlaceKnowledgeDocument).filter(
            PlaceKnowledgeDocument.place_id == entity_id,
            PlaceKnowledgeDocument.expires_at > datetime.utcnow(),
        ).order_by(PlaceKnowledgeDocument.observed_at.desc()).limit(3).all()
        knowledge = " ".join(d.content for d in docs)[:2400]
        if not QdrantService().upsert_place(place.id, place.name, place.city, place.category,
                                           knowledge_text=knowledge):
            raise RuntimeError("Place indexing unavailable")
    elif kind == "travel_tips":
        from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
        repo = SqlVideoRepository(db)
        video = repo.get_by_id(entity_id)
        if video is None or video.status != "completed" or not video.deduplicated_locations:
            return
        if video.travel_tips and (video.travel_tips.get("tips") or video.travel_tips.get("summary")):
            return
        gemini_mode = os.getenv("USE_GEMINI", "false").lower() == "true" or os.getenv("USE_HYBRID", "false").lower() == "true"
        if not (os.getenv("GEMINI_API_KEY") if gemini_mode else os.getenv("OLLAMA_URL")):
            return  # Optional provider is deliberately disabled.
        from app.ml.request_budget import request_budget
        # Tips need only the configured text provider, not YOLO/Whisper/NER.
        with request_budget(150):
            if gemini_mode:
                from app.ml.gemini_service import GeminiService
                tips = GeminiService().generate_travel_tips(
                    video.deduplicated_locations,
                    video_id=entity_id)
            else:
                from app.ml.rag_service import RAGService
                tips = RAGService().generate_travel_tips(video.deduplicated_locations)
        if not tips or not (tips.get("tips") or tips.get("summary")):
            raise RuntimeError("Travel tips provider returned no result")
        repo.save_travel_tips(entity_id, tips)
    else:
        raise ValueError("Unknown deferred work kind")


# ── Ertelenmiş Seyahat İpuçları Task'ı ────────────────────────────────────────

@_celery_app.task(
    name="app.tasks.video_tasks.generate_tips_task",
    queue="video_processing",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    retry_backoff=True,
    acks_late=True,
)
def generate_tips_task(self, video_id: int) -> dict:
    """
    Seyahat ipuçlarını video COMPLETED olduktan sonra üretir.

    Ana pipeline'dan ayrıldı çünkü kullanıcının haritayı ve mekan listesini
    görmesi için ipuçları gerekmiyor; sıralı olarak beklemek toplam süreye
    ~6 saniye ekliyordu.

    Bu task başarısız olursa video COMPLETED kalır ve yalnızca ipuçları
    bölümü boş görünür — pipeline'ın geri kalanındaki graceful degradation
    felsefesiyle tutarlı.
    """
    from app.core.database import SessionLocal
    from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository

    db   = SessionLocal()
    repo = SqlVideoRepository(db)

    try:
        video = repo.get_by_id(video_id)
        if not video:
            logger.warning("İpucu task'ı: video bulunamadı | video_id=%s", video_id)
            return {"status": "skipped", "video_id": video_id}

        locations = video.deduplicated_locations or []
        if not locations:
            logger.info("İpucu task'ı: lokasyon yok, atlanıyor | video_id=%s", video_id)
            return {"status": "skipped", "video_id": video_id}

        processor = _get_processor()
        tips      = processor.generate_travel_tips(locations, video_id)

        repo.save_travel_tips(video_id, tips)
        tip_count = len((tips or {}).get("tips", []))
        logger.info("💡 İpuçları kaydedildi | video_id=%s | %d ipucu", video_id, tip_count)
        return {"status": "completed", "video_id": video_id, "tips": tip_count}

    except Exception as exc:
        logger.error("İpucu task'ı başarısız | video_id=%s | hata: %s", video_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        # Denemeler tükendi — video COMPLETED kalsın, sessizce vazgeç.
        return {"status": "failed", "video_id": video_id}

    finally:
        db.close()


# ── URL Download + Process Task ───────────────────────────────────────────────

@_celery_app.task(
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
    return _process_url_analysis(self, video_id, source_url, source)


@serialized_analysis
def _process_url_analysis(self, video_id: int, source_url: str, source: str = "unknown") -> dict:
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
    video_path = None

    try:
        existing_result = _existing_analysis_result(repo, video_id)
        if existing_result is not None:
            return existing_result
        repo.mark_processing(video_id)
        set_progress(video_id, "downloading", 5)

        # ── Adım 1: URL'i indir ─────────────────────────────────────────────
        video_path = _download_url(source_url, video_id)
        set_progress(video_id, "queued", 10)

        # ── Adım 2: ML pipeline ─────────────────────────────────────────────
        processor = _get_processor()
        # İpuçları ertelenir — bkz. process_video_task.
        result    = processor.process_video(video_path, video_id, defer_tips=True)

        # ── Adım 3: Kaydet ──────────────────────────────────────────────────
        repo.save_results(video_id, result)
        set_progress(video_id, "completed", 100)

        logger.info("✅ URL task tamamlandı | video_id=%s", video_id)
        _notify_push(db, video_id, completed=True)
        _track_trip_created(db, video_id)


        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        if getattr(self, "durable", False):
            raise
        logger.error("⏰ URL task zaman aşımı | video_id=%s", video_id)
        repo.mark_failed(video_id)
        set_progress(video_id, "failed", 0)
        _notify_push(db, video_id, completed=False)
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
        _notify_push(db, video_id, completed=False)
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
            _notify_push(db, video_id, completed=False)
        else:
            set_progress(video_id, "retrying", 0)
        raise

    finally:
        if video_path:
            try:
                if os.path.isfile(video_path):
                    os.remove(video_path)
            except OSError:
                logger.warning("URL geçici dosyası silinemedi | video_id=%s", video_id)
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


@_celery_app.task(name="app.tasks.video_tasks.durable_analysis_task", queue="video_processing",
                  acks_late=True, reject_on_worker_lost=False,
                  soft_time_limit=720, time_limit=780)
def durable_analysis_task(job_id: int):
    from app.core.database import SessionLocal
    from app.application.services.deferred_work import execute_job
    from types import SimpleNamespace
    with SessionLocal() as db:
        def run(kind, video_id):
            from app.models.video import Video
            from app.models.deferred_job import DeferredJob
            from app.application.services.deferred_work import MAX_ATTEMPTS
            if kind != "video_analysis":
                raise ValueError("Unexpected analysis job kind")
            video = db.get(Video, video_id)
            if video is None or video.status == "completed":
                return
            job = db.get(DeferredJob, job_id)
            context = SimpleNamespace(request=SimpleNamespace(retries=job.attempts - 1),
                                      max_retries=MAX_ATTEMPTS - 1, durable=True)
            # SQL job lease handles retries; the same analysis routines retain
            # the PostgreSQL video lock used by older queued Celery tasks.
            context.retry = lambda **kwargs: RuntimeError("Analysis lock busy")
            if video.source_url:
                _process_url_analysis(context, video_id, video.source_url, video.source_platform or "unknown")
            else:
                _process_uploaded_analysis(context, video_id, video.file_path)
        return execute_job(db, job_id, run)
