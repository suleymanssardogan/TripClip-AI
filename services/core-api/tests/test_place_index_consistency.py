"""SQL remains authoritative; a rolled-back place must not enter Qdrant."""
from types import SimpleNamespace
from unittest import mock

import pytest

from app.infrastructure.repositories.sql_place_repository import SqlPlaceRepository
from app.models.place import Place


def _repository():
    db = mock.MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    db.add.side_effect = lambda row: setattr(row, "id", 321) if isinstance(row, Place) else None
    index = mock.MagicMock()
    repo = SqlPlaceRepository(db, qdrant=index)
    video = SimpleNamespace(id=42, user_id=7, deduplicated_locations=[{
        "original_name": "Zeugma Müzesi",
        "place_data": {"location": {"lat": 37.0, "lng": 37.3}},
    }])
    return repo, db, index, video


def test_index_is_published_only_after_sql_commit():
    repo, db, index, video = _repository()
    db.commit.side_effect = lambda: index.upsert_place.assert_not_called()
    repo.sync_from_video(video)
    index.upsert_place.assert_not_called()
    from app.models.deferred_job import DeferredJob
    jobs = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], DeferredJob)]
    assert len(jobs) == 1
    assert (jobs[0].kind, jobs[0].entity_id) == ("place_index", 321)


def test_failed_sql_commit_never_publishes_a_place():
    repo, db, index, video = _repository()
    db.commit.side_effect = RuntimeError("transaction rolled back")
    with pytest.raises(RuntimeError, match="transaction rolled back"):
        repo.sync_from_video(video)
    index.upsert_place.assert_not_called()


def test_index_failure_does_not_invalidate_committed_places():
    repo, db, index, video = _repository()
    index.upsert_place.side_effect = RuntimeError("Qdrant unavailable")
    repo.sync_from_video(video)
    db.commit.assert_called_once()
