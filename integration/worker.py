"""Test-only worker: production task and SQL workflow, deterministic AI stand-in."""
import os
import time
from pathlib import Path
from sqlalchemy import text
from app.core.database import engine
from app.core.celery_app import celery_app
from app.tasks import video_tasks


class SyntheticProcessor:
    def process_video(self, path, video_id, defer_tips=True):
        with engine.begin() as db:
            db.execute(text("INSERT INTO integration_runs(video_id) VALUES (:id)"), {"id": video_id})
        if Path(path).read_bytes() == b"slow":
            time.sleep(120)
        return {"duration": 1, "deduplicated_locations": []}


video_tasks._get_processor = SyntheticProcessor
video_tasks._notify_push = lambda *args, **kwargs: None
video_tasks._track_trip_created = lambda *args, **kwargs: None
# Deterministic vectors isolate queue/index infrastructure from model downloads.
from app.ml import qdrant_service
qdrant_service._create_embedding_model = lambda: SyntheticEmbedding()


class SyntheticEmbedding:
    def encode(self, text):
        import numpy as np
        return np.array([1.0] + [0.0] * 383)


if __name__ == "__main__":
    celery_app.worker_main(["worker", "--pool=prefork", "--concurrency=2", "-Q", "video_processing",
                           "--loglevel=INFO", "--without-gossip", "--without-mingle"])
