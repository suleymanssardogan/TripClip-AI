from unittest import mock

from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
from app.models.video import VideoStatus


def test_library_job_commits_with_video_before_immediate_attempt():
    db = mock.MagicMock()
    video = mock.MagicMock()
    repo = SqlVideoRepository(db)
    def attempt(session, job_id, handler):
        assert session is db
        db.commit.assert_called_once()
        assert video.status == VideoStatus.COMPLETED
        return "pending"  # Failure is retained by the durable executor.

    with mock.patch.object(repo, "get_by_id", return_value=video), \
         mock.patch("app.application.services.deferred_work.execute_job", side_effect=attempt) as execute:
        repo.save_results(42, {"duration": 12})
    assert video.status == VideoStatus.COMPLETED
    db.commit.assert_called_once()
    execute.assert_called_once()
    jobs = [call.args[0] for call in db.add.call_args_list]
    assert {job.kind for job in jobs} >= {"travel_tips", "library_sync"}
