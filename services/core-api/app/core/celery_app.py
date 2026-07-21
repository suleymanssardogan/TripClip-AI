"""
TripClip AI — Celery Uygulama Konfigürasyonu.

Broker  : Redis (db=0)
Backend : Redis (db=2)  ← task sonuçları/durumları burada saklanır

Worker başlatmak için:
    celery -A app.core.celery_app worker --loglevel=info -Q video_processing
"""
import os
import time
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_ready
from prometheus_client import Counter, Histogram, start_http_server

logger = logging.getLogger("tripclip.celery.metrics")

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


# ── Prometheus metrikleri ──────────────────────────────────────────────────────
#
# Bu modül hem API sunucusu (task.delay() çağırmak için) hem de gerçek Celery
# worker process'i tarafından import edilir. Sinyal handler'ları her ikisinde
# de kayıt olur (zararsız — sadece worker task çalıştırdığında tetiklenirler),
# ama start_http_server() SADECE worker_ready'de çağrılır — bu sinyal yalnızca
# gerçek `celery worker` process'inde tetiklenir, API sunucusunda asla.

CELERY_TASKS_TOTAL = Counter(
    "celery_tasks_total",
    "Toplam işlenen Celery task sayısı (task adı ve sonuç durumuna göre)",
    ["task_name", "status"],
)
CELERY_TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Celery task işlem süresi (saniye)",
    ["task_name"],
)

_task_start_times: dict[str, float] = {}


@task_prerun.connect
def _on_task_prerun(sender=None, task_id=None, task=None, **kwargs):
    _task_start_times[task_id] = time.perf_counter()


@task_postrun.connect
def _on_task_postrun(sender=None, task_id=None, task=None, state=None, **kwargs):
    task_name = getattr(task, "name", None) or getattr(sender, "name", None) or "unknown"
    start = _task_start_times.pop(task_id, None)
    if start is not None:
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(time.perf_counter() - start)
    status = (state or "unknown").lower()
    CELERY_TASKS_TOTAL.labels(task_name=task_name, status=status).inc()


def _start_multiprocess_metrics_server(port: int) -> None:
    """Prometheus multiprocess mode uyumlu HTTP sunucusu.

    `--pool=prefork` ile her forked child kendi Counter/Histogram verilerini
    PROMETHEUS_MULTIPROC_DIR altındaki dosyalara yazar (Counter/Histogram
    tanımları hiç değişmez — prometheus_client bu env var set olduğunda
    otomatik multiprocess-safe depolamaya geçer). start_http_server() varsayılan
    olarak TEK process'in in-memory registry'sini sunar — prefork'ta child'lar
    ayrı process olduğu için bu, diğer child'ların metriklerini görünmez kılar.
    Bu sunucu, her scrape'te MultiProcessCollector ile TÜM process'lerin
    dosyalarını birleştirip tek bir yanıt döner.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST, multiprocess
    import threading

    class _MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass  # varsayılan stdout access-log gürültüsünü sustur

    server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


@worker_ready.connect
def _on_worker_ready(**kwargs):
    port = int(os.getenv("CELERY_METRICS_PORT", "9808"))
    try:
        if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
            _start_multiprocess_metrics_server(port)
        else:
            # --pool=solo / tek process (örn. local geliştirme) — basit sunucu yeterli.
            start_http_server(port)
        logger.info("📊 Celery metrics server started on :%d", port)
    except OSError as exc:
        logger.warning("Celery metrics server başlatılamadı (:%d): %s", port, exc)
