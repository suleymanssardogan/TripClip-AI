from unittest import mock

from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
from app.models.video import VideoStatus


def test_optional_place_sync_rollback_preserves_completed_video():
    db = mock.MagicMock()
    video = mock.MagicMock()
    repo = SqlVideoRepository(db)
    with mock.patch.object(repo, "get_by_id", return_value=video), \
         mock.patch("app.infrastructure.repositories.sql_video_repository.SqlPlaceRepository") as places:
        places.return_value.sync_from_video.side_effect = RuntimeError("SQL sync failed")
        repo.save_results(42, {"duration": 12})
    assert video.status == VideoStatus.COMPLETED
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
