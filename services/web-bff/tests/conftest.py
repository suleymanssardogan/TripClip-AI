"""
Pytest fixtures — FastAPI test client + Core API çağrılarını mock'lama.

core-api/tests/conftest.py ile aynı desen: env değişkenleri app import
edilmeden önce set edilir, testler gerçek core-api'ye veya DB'ye bağlanmaz.
"""
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-tripclip-ai-2026")
os.environ.setdefault("CORE_API_URL", "http://core-api-test:8000")

from unittest import mock

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.auth import SECRET_KEY, ALGORITHM


@pytest.fixture(scope="function")
def client():
    """Her test için temiz bir test client — gerçek ağ çağrısı yapılmaz."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Her testten önce rate limiter sayaçlarını sıfırla (core-api/mobile-bff conftest ile aynı desen)."""
    from app.main import limiter as main_limiter
    from app.routes.auth import limiter as auth_limiter
    from app.routes.trip_sharing import limiter as trip_sharing_limiter
    from app.routes.trip_assistant import limiter as trip_assistant_limiter
    main_limiter.reset()
    auth_limiter.reset()
    trip_sharing_limiter.reset()
    trip_assistant_limiter.reset()
    yield


def _make_token(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id)}, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture
def make_auth_headers():
    """Belirli bir user_id için geçerli Authorization header üretir."""
    def _make(user_id: int = 1):
        return {"Authorization": f"Bearer {_make_token(user_id)}"}
    return _make


@pytest.fixture
def auth_headers(make_auth_headers):
    """Varsayılan user_id=1 için geçerli Authorization header."""
    return make_auth_headers(1)


class MockResponse:
    """httpx.Response test double'ı — route kodunun kullandığı .status_code / .json() yeterli."""

    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


@pytest.fixture
def make_response():
    """MockResponse sınıfını fixture olarak sağlar (tests/ modüller arası import yerine)."""
    return MockResponse


@pytest.fixture
def mock_core_api():
    """
    Core API'ye giden httpx.AsyncClient.get/post çağrılarını mock'lar.

    Kullanım:
        mock_core_api.post.return_value = make_response(200, {...})
        resp = client.post(...)
        mock_core_api.post.assert_awaited_once()
    """
    with mock.patch("httpx.AsyncClient.post", new_callable=mock.AsyncMock) as mock_post, \
         mock.patch("httpx.AsyncClient.get", new_callable=mock.AsyncMock) as mock_get, \
         mock.patch("httpx.AsyncClient.delete", new_callable=mock.AsyncMock) as mock_delete:
        holder = mock.Mock()
        holder.post = mock_post
        holder.get = mock_get
        holder.delete = mock_delete
        yield holder
