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

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


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
