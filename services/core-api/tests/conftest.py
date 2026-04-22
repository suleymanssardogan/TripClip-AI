"""
Pytest fixtures — SQLite in-memory test DB, FastAPI test client
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL",    "redis://localhost:6379/1")
os.environ.setdefault("MONGODB_URL",  "mongodb://localhost:27017/tripclip_test")
os.environ.setdefault("SECRET_KEY",   "test-secret-key-tripclip-ai-2026")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# SQLite in-memory (hızlı, izole)
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Test başında tabloları oluştur, test sonunda sil"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Her test için temiz bir test client"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def registered_user(client):
    """Kayıtlı kullanıcı + token döndür"""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@tripclip.test"
    resp = client.post("/internal/auth/register", json={
        "email": email,
        "password": "Test1234!",
        "username": f"user_{uuid.uuid4().hex[:6]}"
    })
    assert resp.status_code == 200
    data = resp.json()
    return {"email": email, "password": "Test1234!", "token": data["access_token"], "user_id": data["user_id"]}


@pytest.fixture(scope="function")
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['token']}"}
