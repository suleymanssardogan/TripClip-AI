"""
TripClip AI — Redis Bağlantı Yöneticisi.

Kullanım:
    from app.core.redis import get_redis, progress_redis

    r = get_redis()          # genel amaçlı (db=0)
    p = progress_redis()     # progress tracking (db=1)
"""
import os
import logging
import redis
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# video_processing kuyruğu Celery broker'ın (db=0) Redis list'i olarak tutulur —
# scripts/monitor.sh'te elle yapılan `redis-cli LLEN video_processing` kontrolünün
# Prometheus'a taşınmış hali.
CELERY_QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Celery video_processing kuyruğunda bekleyen task sayısı",
)


def _make_client(db_override: int | None = None) -> redis.Redis | None:
    """Redis bağlantısı oluştur. Başarısız olursa None döner (graceful degradation)."""
    try:
        url = REDIS_URL
        client = redis.Redis.from_url(
            url,
            db=db_override,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis bağlantısı kurulamadı: %s — özellik devre dışı.", exc)
        return None


# ── Singleton clients (lazy) ──────────────────────────────────────────────────

_general_client:  redis.Redis | None = None
_progress_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Genel amaçlı Redis client (db=0)."""
    global _general_client
    if _general_client is None:
        _general_client = _make_client(db_override=0)
    return _general_client


def progress_redis() -> redis.Redis | None:
    """Video progress tracking için Redis client (db=1)."""
    global _progress_client
    if _progress_client is None:
        _progress_client = _make_client(db_override=1)
    return _progress_client


# ── Progress yardımcıları ─────────────────────────────────────────────────────

def set_progress(video_id: int, stage: str, percent: int, ttl: int = 600) -> None:
    """Video işleme aşamasını Redis'e yaz."""
    import json
    r = progress_redis()
    if r:
        try:
            r.setex(
                f"progress:{video_id}",
                ttl,
                json.dumps({"stage": stage, "percent": percent}),
            )
        except Exception as exc:
            logger.debug("Progress yazılamadı: %s", exc)


def get_progress(video_id: int) -> dict | None:
    """Video işleme aşamasını Redis'ten oku."""
    import json
    r = progress_redis()
    if not r:
        return None
    try:
        raw = r.get(f"progress:{video_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


# ── Kullanıcı başına günlük işleme kotası ─────────────────────────────────────
#
# USE_GEMINI=true olduğunda her video işlenirken en az 2 Gemini API çağrısı
# yapılır (extract_locations + generate_travel_tips) — GeminiService kendi
# içinde tek çağrı başına maliyeti sınırlar (frame/token capleri) ama
# script'lenmiş bir hesabın çok sayıda video yükleyip toplam maliyeti sınırsız
# şekilde büyütmesine karşı bir üst sınır yoktu. Bu sayaç, kullanıcı başına
# günlük video işleme sayısını (dolayısıyla Gemini çağrı sayısını) sınırlar.

def check_and_increment_daily_quota(user_id: int, limit: int) -> tuple[bool, int]:
    """
    Kullanıcının günlük video işleme sayacını atomik olarak arttırır.

    Redis erişilemezse (bkz. get_redis) kota uygulanamaz — bu kodun geri
    kalanındaki her yerde kullanılan "graceful degradation" felsefesiyle
    tutarlı şekilde fail-open davranır: upload engellenmez, sadece kota
    özelliği o an devre dışı kalır.

    Returns:
        (izin_verildi_mi, bugünkü_güncel_sayaç)
    """
    r = get_redis()
    if not r:
        return True, 0
    try:
        from datetime import datetime, timezone
        key = f"quota:daily_uploads:{user_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, 26 * 3600)  # gün dönümü + tampon
        return count <= limit, count
    except Exception as exc:
        logger.warning("Günlük kota kontrolü başarısız — fail-open: %s", exc)
        return True, 0


# ── Prometheus queue-depth gauge'u ────────────────────────────────────────────

def update_queue_depth_metric() -> None:
    """Redis'ten video_processing kuyruk uzunluğunu okuyup gauge'u günceller.

    core-api'nin FastAPI lifespan'inde periyodik olarak çağrılır.
    """
    r = get_redis()
    if not r:
        return
    try:
        CELERY_QUEUE_DEPTH.set(r.llen("video_processing"))
    except Exception as exc:
        logger.debug("Queue depth okunamadı: %s", exc)
