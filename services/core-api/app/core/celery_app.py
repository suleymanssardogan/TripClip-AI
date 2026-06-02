"""
TripClip AI — Celery Uygulama Konfigürasyonu.

Broker  : Redis (db=0)
Backend : Redis (db=2)  ← task sonuçları/durumları burada saklanır

Worker başlatmak için:
    celery -A app.core.celery_app worker --loglevel=info -Q video_processing
"""
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Broker: mesajlar buraya konur (db=0)
# Backend: task sonuçları burada saklanır (db=2)
celery_app = Celery(
    "tripclip",
    broker=REDIS_URL,
    backend=REDIS_URL.replace("/0", "/2"),
    include=["app.tasks.video_tasks"],   # ← task modülleri
)

celery_app.conf.update(
    # ── Serileştirme ───────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # ── Zaman ayarları ─────────────────────────────────────────────────────────
    task_soft_time_limit=900,   # 15 dk → SoftTimeLimitExceeded fırlatır
    task_time_limit=1200,       # 20 dk → hard kill (Gemini + Nominatim için yeterli)
    result_expires=3600,        # sonuçlar 1 saat Redis'te kalır

    # ── Kuyruk tanımı ──────────────────────────────────────────────────────────
    task_default_queue="video_processing",
    task_queues={
        "video_processing": {
            "exchange": "video_processing",
            "routing_key": "video_processing",
        },
    },

    # ── Güvenilirlik ───────────────────────────────────────────────────────────
    task_acks_late=True,            # worker crash → task yeniden kuyruğa girer
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # worker başına 1 task (ML işlem ağır)

    # ── Timezone ───────────────────────────────────────────────────────────────
    timezone="Europe/Istanbul",
    enable_utc=True,
)
