"""Independent outbox dispatcher and retention process; no HTTP API dependency."""
import argparse
import logging
import os
from pathlib import Path
import signal
import threading
import time

logger = logging.getLogger("tripclip.maintenance")


def settings():
    dispatch = float(os.getenv("MAINTENANCE_DISPATCH_INTERVAL", "5"))
    retention = float(os.getenv("MAINTENANCE_RETENTION_INTERVAL", "900"))
    if not 1 <= dispatch <= 60 or not 30 <= retention <= 86400:
        raise ValueError("Maintenance intervals must be dispatch 1-60s, retention 30-86400s")
    root = Path(os.getenv("MAINTENANCE_HEALTH_DIR", "/tmp/tripclip-maintenance"))
    return {"dispatch": dispatch, "retention": retention}, root


def run_periodic(name, callback, interval, stop, root):
    heartbeat = root / name
    while not stop.is_set():
        try:
            callback()
        except Exception as exc:
            # A transient service failure must not stop the retry scheduler.
            logger.warning("Maintenance job failed | job=%s | error=%s", name, type(exc).__name__)
        heartbeat.write_text(str(time.time()))
        if stop.wait(interval):
            break


def healthy(intervals, root, now=None):
    now = time.time() if now is None else now
    try:
        return all(0 <= now - float((root / name).read_text()) <= interval + 60
                   for name, interval in intervals.items())
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    intervals, root = settings()
    if args.healthcheck:
        return 0 if healthy(intervals, root) else 1
    logging.basicConfig(level=logging.INFO)
    from app.core.migrations import run_migrations
    from app.application.services.deferred_work import dispatch_pending_work
    from app.application.services.privacy_retention import sweep_upload_retention
    # Uses the same PostgreSQL migration lock as API startup, independently.
    run_migrations()
    from prometheus_client import start_http_server
    start_http_server(int(os.getenv("MAINTENANCE_METRICS_PORT", "9810")))
    root.mkdir(parents=True, exist_ok=True)
    for name in intervals:
        (root / name).unlink(missing_ok=True)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    from app.application.services.apple_credentials import dispatch_revocations
    def dispatch():
        dispatch_revocations()
        dispatch_pending_work()
    callbacks = {"dispatch": dispatch, "retention": sweep_upload_retention}
    threads = [threading.Thread(target=run_periodic, name=name, daemon=True,
                                args=(name, callbacks[name], interval, stop, root))
               for name, interval in intervals.items()]
    for thread in threads:
        thread.start()
    logger.info("Maintenance service started")
    failed = False
    try:
        while not stop.wait(1):
            if any(not thread.is_alive() for thread in threads):
                failed = True
                break
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=5)
        for name in intervals:
            (root / name).unlink(missing_ok=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
