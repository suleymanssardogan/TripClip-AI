import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import pytest
import requests


def eventually(check, timeout=30):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(0.2)
    raise AssertionError(f"Condition not reached in {timeout}s; last error={last}")


@pytest.fixture(scope="session")
def infrastructure():
    assert os.getenv("TRIPCLIP_INTEGRATION") == "1", "Integration opt-in required"
    from sqlalchemy import text
    from app.core.database import engine
    assert engine.url.database == "tripclip_integration", "Refusing non-test database"
    proxy = os.environ["TOXIPROXY_URL"]
    eventually(lambda: requests.get(proxy + "/version", timeout=2).ok)
    for name, port, upstream in [("redis", 16379, "redis:6379"), ("qdrant", 16333, "qdrant:6333")]:
        response = requests.post(proxy + "/proxies", json={"name": name, "listen": f"0.0.0.0:{port}",
                                                          "upstream": upstream, "enabled": True}, timeout=3)
        response.raise_for_status()
    eventually(lambda: requests.get(os.environ["QDRANT_URL"] + "/collections", timeout=2).ok)
    from alembic import command
    from alembic.config import Config
    cfg = Config("alembic.ini"); command.upgrade(cfg, "head")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE integration_runs (id SERIAL PRIMARY KEY, video_id INTEGER NOT NULL)"))
    yield proxy
    engine.dispose()


@pytest.fixture
def proxy(infrastructure):
    def enable(name, value):
        response = requests.post(infrastructure + f"/proxies/{name}", json={"enabled": value}, timeout=3)
        response.raise_for_status()
    yield enable
    enable("redis", True); enable("qdrant", True)


@pytest.fixture
def database(infrastructure):
    from sqlalchemy import text
    from app.core.database import engine, SessionLocal
    # All operations target only the disposable, explicitly named database.
    import redis
    for number in (0, 1, 2):
        client = redis.Redis(host="redis", port=6379, db=number, socket_timeout=3)
        client.flushdb(); client.close()
    with engine.begin() as db:
        db.execute(text("TRUNCATE users, videos, deferred_jobs, places, integration_runs CASCADE"))
    from app.models.user import User
    with SessionLocal() as db:
        db.add(User(id=1, username="synthetic", email="synthetic@example.test")); db.commit()
    return SessionLocal


@pytest.fixture
def workers(database):
    children = []
    def start():
        log_path = Path("/reports") / f"worker-{len(children)}-{time.time_ns()}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("w")
        process = subprocess.Popen([sys.executable, "-m", "integration.worker"], stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        children.append((process, log))
        from app.core.celery_app import celery_app
        eventually(lambda: process.poll() is None and celery_app.control.ping(timeout=0.5), timeout=30)
        return process
    def kill(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    yield start, kill
    for process, log in children:
        kill(process); log.close()


@pytest.fixture
def maintenance(database):
    children = []
    def start():
        import tempfile
        health_dir = tempfile.mkdtemp(prefix="maintenance-health-")
        env = dict(os.environ, MAINTENANCE_HEALTH_DIR=health_dir,
                   MAINTENANCE_DISPATCH_INTERVAL="1", MAINTENANCE_RETENTION_INTERVAL="30")
        log = (Path("/reports") / f"maintenance-{time.time_ns()}.log").open("w")
        process = subprocess.Popen([sys.executable, "-m", "app.tasks.maintenance"], env=env,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        children.append((process, log, health_dir))
        eventually(lambda: process.poll() is None and (Path(health_dir) / "dispatch").exists())
        return process, health_dir
    yield start
    for process, log, health_dir in children:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        log.close()
