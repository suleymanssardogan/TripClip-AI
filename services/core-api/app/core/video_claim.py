"""Connection-held PostgreSQL lock shared by upload and URL workers."""
from contextlib import contextmanager
from functools import wraps
from sqlalchemy import text


@contextmanager
def analysis_claim(video_id, engine):
    # SQLite is only used for local development/tests. Production uses Postgres.
    if engine.dialect.name == "sqlite":
        yield True
        return
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Video claim requires PostgreSQL")
    with engine.connect() as connection:
        with connection.begin():
            acquired = bool(connection.execute(text(
                "SELECT pg_try_advisory_xact_lock(:namespace, :video_id)"),
                {"namespace": 73419, "video_id": video_id}).scalar())
            # Transaction end or worker connection death releases the lock.
            yield acquired


def serialized_analysis(function):
    @wraps(function)
    def run(task, video_id, *args, **kwargs):
        from app.core.database import engine
        with analysis_claim(video_id, engine) as acquired:
            if not acquired:
                # A competing delivery must not start the expensive pipeline.
                # Allow this short contention retry independently of AI retries.
                raise task.retry(countdown=30, max_retries=30)
            return function(task, video_id, *args, **kwargs)
    return run
