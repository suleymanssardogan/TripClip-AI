from datetime import datetime
from unittest.mock import patch
import pytest
from app.core import http_pool
from app.models.video import Video, VideoStatus
from app.models.trip import Trip
from app.models.trip_collaborator import TripCollaborator, CollaboratorRole
from app.infrastructure.repositories.sql_video_repository import SqlVideoRepository
from app.infrastructure.repositories.sql_trip_repository import SqlTripRepository
from conftest import TestingSessionLocal


def test_video_pages_are_bounded_stable_and_user_scoped(client, registered_user):
    uid = registered_user["user_id"]
    with TestingSessionLocal() as db:
        rows = [Video(user_id=uid, filename=f"video-{i}", file_path=f"/tmp/{i}",
                      status=VideoStatus.UPLOADED, created_at=datetime(2026, 1, 1)) for i in range(23)]
        db.add_all(rows); db.commit()
        ids = sorted([v.id for v in rows], reverse=True)
        db.add(Video(user_id=uid + 999, filename="other", file_path="/tmp/other")); db.commit()
        repo = SqlVideoRepository(db)
        assert repo.count_by_user(uid) == 23
        assert [v.id for v in repo.get_by_user(uid, limit=20)] == ids[:20]
        assert [v.id for v in repo.get_by_user(uid, limit=20, offset=20)] == ids[20:]
    response = client.get(f"/internal/videos/user/{uid}?limit=20").json()
    assert response["total"] == 23
    assert response["has_more"] is True
    assert response["limit"] == 20
    last = client.get(f"/internal/videos/user/{uid}?limit=20&offset=20").json()
    assert len(last["plans"]) == 3 and last["has_more"] is False


def test_trip_page_merges_owned_and_shared_without_duplicates(client, registered_user):
    uid = registered_user["user_id"]
    with TestingSessionLocal() as db:
        owned = Trip(user_id=uid, title="owned", created_at=datetime(2026, 1, 1))
        shared = Trip(user_id=uid + 999, title="shared", created_at=datetime(2026, 1, 1))
        hidden = Trip(user_id=uid + 999, title="hidden")
        db.add_all([owned, shared, hidden]); db.flush()
        db.add(TripCollaborator(trip_id=shared.id, user_id=uid, role=CollaboratorRole.VIEWER))
        db.commit()
        repo = SqlTripRepository(db)
        assert repo.count_trips(uid) == 2
        assert repo.list_trips(uid, limit=1)[0]["id"] == shared.id
        assert repo.list_trips(uid, limit=1)[0]["role"] == "viewer"
        assert repo.list_trips(uid, limit=1, offset=1)[0]["id"] == owned.id


@pytest.mark.parametrize("url", ["/internal/trips?limit=51", "/internal/trips?offset=-1",
    "/internal/videos/user/1?limit=0", "/internal/videos/public?offset=-1"])
def test_invalid_pages_rejected(client, url):
    assert client.get(url, headers={"x-user-id": "1"}).status_code == 422


def test_provider_pool_is_shared_without_cookie_or_header_leakage():
    sessions = []
    adapters = []
    def capture(session, method, url, **kwargs):
        sessions.append(session)
        adapters.append(session.adapters["https://"].adapter)
        assert not session.cookies
        assert "X-User" not in session.headers
        session.cookies.set("secret", "private")
        session.headers["X-User"] = "private"
        return object()
    try:
        with patch("requests.Session.request", capture):
            http_pool.get("https://example.invalid", timeout=5)
            http_pool.post("https://example.invalid", timeout=10)
        assert sessions[0] is not sessions[1]
        assert adapters[0] is adapters[1]
        assert adapters[0].max_retries.total == 0
    finally:
        http_pool.close_pool()


def test_provider_pool_requires_timeout_and_consumed_responses():
    with pytest.raises(ValueError):
        http_pool.get("https://example.invalid")
    with pytest.raises(ValueError):
        http_pool.get("https://example.invalid", timeout=5, stream=True)
