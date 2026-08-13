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


# ─── Refresh — REFRESH_TOKEN_* status-code regression (M34) ─────────────────
# mobile-bff ile aynı boşluk web-bff'de de vardı: bu kodlar _WEB_MESSAGES'ta
# hiç kayıtlı değildi ve varsayılan 400'e düşüyordu; core-api hepsini 401
# döndürür. Bkz. mobile-bff/tests/test_auth.py'deki aynı regresyon testi.
import pytest


@pytest.mark.parametrize("code", [
    "REFRESH_TOKEN_INVALID", "REFRESH_TOKEN_EXPIRED", "REFRESH_TOKEN_REUSED", "REFRESH_TOKEN_RACE_LOST",
])
def test_refresh_token_error_codes_map_to_401(client, mock_core_api, make_response, code):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": code, "message": "invalid"},
    })

    resp = client.post("/api/web/auth/refresh", json={"refresh_token": "sometoken"})

    assert resp.status_code == 401
    assert resp.json()["code"] == code


# ─── FORBIDDEN / SHARE_NOT_FOUND status-code regression (M38) ───────────────
# mobile-bff bu ikisini zaten doğru eşliyordu (403/404); web-bff'de hiç
# kayıtlı değillerdi ve varsayılan 400'e düşüyorlardı — aynı core-api
# durumu iOS kullanıcıları için doğru anlamı taşırken, web kullanıcıları
# için "geçersiz istek" gibi görünüyordu (cross-platform contract
# asimetrisi).

def test_forbidden_error_code_maps_to_403(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(403, {
        "error": {"code": "FORBIDDEN", "message": "forbidden"},
    })

    resp = client.post("/api/web/auth/refresh", json={"refresh_token": "sometoken"})

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_share_not_found_error_code_maps_to_404(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(404, {
        "error": {"code": "SHARE_NOT_FOUND", "message": "not found"},
    })

    resp = client.post("/api/web/auth/refresh", json={"refresh_token": "sometoken"})

    assert resp.status_code == 404
    assert resp.json()["code"] == "SHARE_NOT_FOUND"


# ─── Google Sign-In proxy ─────────────────────────────────────────────────────

def test_google_sign_in_happy_path_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token", "token_type": "bearer", "user_id": 9, "email": "g@test.com",
    })

    resp = client.post("/api/web/auth/google", json={"code": "authcode", "redirect_uri": "http://localhost:3000/auth/google/callback"})

    assert resp.status_code == 200
    assert resp.json()["user_id"] == 9


def test_google_sign_in_unverified_email_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": "GOOGLE_EMAIL_NOT_VERIFIED", "message": "unverified"},
    })

    resp = client.post("/api/web/auth/google", json={"code": "authcode", "redirect_uri": "http://localhost:3000/auth/google/callback"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "GOOGLE_EMAIL_NOT_VERIFIED"


# ─── Forgot / Reset Password proxy ────────────────────────────────────────────

def test_forgot_password_always_returns_generic_status(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"status": "ok"})

    resp = client.post("/api/web/auth/forgot-password", json={"email": "anything@test.com"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_reset_password_expired_token_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": "PASSWORD_RESET_TOKEN_EXPIRED", "message": "expired"},
    })

    resp = client.post("/api/web/auth/reset-password", json={"token": "abc", "new_password": "NewSecure123!"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "PASSWORD_RESET_TOKEN_EXPIRED"
