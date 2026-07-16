"""
Web BFF — Auth endpoint testleri.

Core API gerçekten çağrılmaz; httpx.AsyncClient mock'lanır (mock_core_api fixture).
"""


# ─── Register ───────────────────────────────────────────────────────────────

def test_register_happy_path(client, mock_core_api, make_response):
    """Core API 200 dönerse, BFF aynı gövdeyi olduğu gibi iletir."""
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token",
        "token_type": "bearer",
        "user_id": 42,
        "email": "new@test.com",
    })

    resp = client.post("/api/web/auth/register", json={
        "email": "new@test.com",
        "password": "Secure123!",
        "username": "newuser",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "fake-token"
    assert data["user_id"] == 42
    mock_core_api.post.assert_awaited_once()


def test_register_invalid_payload_missing_password(client, mock_core_api):
    """Şifre alanı eksikse Core API'ye hiç gidilmeden 422 dönmeli."""
    resp = client.post("/api/web/auth/register", json={"email": "x@x.com"})
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_register_duplicate_email_passthrough(client, mock_core_api, make_response):
    """Core API 400 DUPLICATE_EMAIL dönerse, BFF web dostu mesaja çevirmeli."""
    mock_core_api.post.return_value = make_response(400, {
        "error": {"code": "DUPLICATE_EMAIL", "message": "already registered"},
    })

    resp = client.post("/api/web/auth/register", json={
        "email": "dup@test.com",
        "password": "Secure123!",
    })

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "DUPLICATE_EMAIL"
    assert "mevcut" in body["message"].lower()


# ─── Login ──────────────────────────────────────────────────────────────────

def test_login_happy_path(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token",
        "token_type": "bearer",
        "user_id": 7,
        "email": "user@test.com",
    })

    resp = client.post("/api/web/auth/login", json={
        "email": "user@test.com",
        "password": "whatever",
    })

    assert resp.status_code == 200
    assert resp.json()["access_token"] == "fake-token"


def test_login_wrong_credentials_passthrough(client, mock_core_api, make_response):
    """Core API 401 AUTH_ERROR dönerse, BFF de 401 dönmeli."""
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": "AUTH_ERROR", "message": "invalid credentials"},
    })

    resp = client.post("/api/web/auth/login", json={
        "email": "user@test.com",
        "password": "wrong",
    })

    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_ERROR"


def test_login_invalid_payload_missing_email(client, mock_core_api):
    resp = client.post("/api/web/auth/login", json={"password": "x"})
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_login_core_api_unreachable(client, mock_core_api):
    """Core API'ye ulaşılamazsa 503 SERVICE_UNAVAILABLE dönmeli (crash etmemeli)."""
    import httpx
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")

    resp = client.post("/api/web/auth/login", json={
        "email": "user@test.com",
        "password": "whatever",
    })

    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


# ─── Apple Sign In ────────────────────────────────────────────────────────────

def test_apple_sign_in_invalid_payload(client, mock_core_api):
    """identity_token eksikse Core API'ye hiç gidilmeden 422 dönmeli."""
    resp = client.post("/api/web/auth/apple", json={})
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_apple_sign_in_happy_path(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token",
        "token_type": "bearer",
        "user_id": 3,
        "email": "apple@test.com",
    })

    resp = client.post("/api/web/auth/apple", json={"identity_token": "fake-jwt"})

    assert resp.status_code == 200
    assert resp.json()["user_id"] == 3
