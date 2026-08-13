"""
Mobile BFF — Auth endpoint testleri.

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

    resp = client.post("/api/mobile/auth/register", json={
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
    resp = client.post("/api/mobile/auth/register", json={"email": "x@x.com"})
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_register_duplicate_email_passthrough(client, mock_core_api, make_response):
    """Core API 400 DUPLICATE_EMAIL dönerse, BFF iOS dostu mesaja çevirmeli."""
    mock_core_api.post.return_value = make_response(400, {
        "error": {"code": "DUPLICATE_EMAIL", "message": "already registered"},
    })

    resp = client.post("/api/mobile/auth/register", json={
        "email": "dup@test.com",
        "password": "Secure123!",
    })

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "DUPLICATE_EMAIL"
    assert "kayıtlı" in body["message"].lower()


# ─── Login ──────────────────────────────────────────────────────────────────

def test_login_happy_path(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token",
        "token_type": "bearer",
        "user_id": 7,
        "email": "user@test.com",
    })

    resp = client.post("/api/mobile/auth/login", json={
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

    resp = client.post("/api/mobile/auth/login", json={
        "email": "user@test.com",
        "password": "wrong",
    })

    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_ERROR"


def test_login_invalid_payload_missing_email(client, mock_core_api):
    resp = client.post("/api/mobile/auth/login", json={"password": "x"})
    assert resp.status_code == 422
    mock_core_api.post.assert_not_awaited()


def test_login_core_api_unreachable(client, mock_core_api):
    """Core API'ye ulaşılamazsa 503 SERVICE_UNAVAILABLE dönmeli (crash etmemeli)."""
    import httpx
    mock_core_api.post.side_effect = httpx.ConnectError("connection refused")

    resp = client.post("/api/mobile/auth/login", json={
        "email": "user@test.com",
        "password": "whatever",
    })

    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


# ─── Device Token (Push Notifications) ───────────────────────────────────────

def test_device_token_happy_path(client, mock_core_api, make_response, auth_headers):
    mock_core_api.put.return_value = make_response(200, {"status": "ok"})

    resp = client.put(
        "/api/mobile/auth/device-token",
        json={"token": "abc123"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_core_api.put.assert_awaited_once()
    # user_id JWT'den çözülüp core-api'ye x-user-id header'ı olarak iletilmeli
    _, kwargs = mock_core_api.put.call_args
    assert kwargs["headers"]["x-user-id"] == "1"
    assert kwargs["json"] == {"token": "abc123"}


def test_device_token_without_auth_returns_403(client, mock_core_api):
    """Authorization header'ı yoksa core-api'ye hiç gidilmeden reddedilmeli
    (HTTPBearer, eksik header için FastAPI varsayılanı olarak 403 döner —
    401 yalnızca geçersiz/süresi dolmuş bir token için kullanılır)."""
    resp = client.put("/api/mobile/auth/device-token", json={"token": "abc123"})
    assert resp.status_code == 403
    mock_core_api.put.assert_not_awaited()


def test_device_token_core_api_error_passthrough(client, mock_core_api, make_response, auth_headers):
    mock_core_api.put.return_value = make_response(401, {
        "error": {"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
    })

    resp = client.put(
        "/api/mobile/auth/device-token",
        json={"token": "abc123"},
        headers=auth_headers,
    )

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


# ─── Refresh — REFRESH_TOKEN_* status-code regression (M34) ─────────────────
# Bu kodlar daha önce _MOBILE_MESSAGES'ta hiç kayıtlı DEĞİLDİ ve varsayılan
# 400'e düşüyordu; core-api hepsini 401 döndürür. iOS `apiError.isUnauthorized`
# kontrolü YALNIZCA gerçek 401'de doğru tetiklenir — bu yüzden bu regresyon
# testleri kalıcı olarak buraya eklendi (bkz. Milestone 26'nın aynı sınıf
# hataya karşı uyarısı).
import pytest


@pytest.mark.parametrize("code", [
    "REFRESH_TOKEN_INVALID", "REFRESH_TOKEN_EXPIRED", "REFRESH_TOKEN_REUSED", "REFRESH_TOKEN_RACE_LOST",
])
def test_refresh_token_error_codes_map_to_401(client, mock_core_api, make_response, code):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": code, "message": "invalid"},
    })

    resp = client.post("/api/mobile/auth/refresh", json={"refresh_token": "sometoken"})

    assert resp.status_code == 401
    assert resp.json()["code"] == code


# ─── SERVICE_UNAVAILABLE status-code regression (M38) ───────────────────────
# web-bff bu kodu zaten 503'e eşliyordu; mobile-bff'de hiç kayıtlı değildi
# ve varsayılan 400'e düşüyordu — aynı core-api durumu iOS kullanıcıları
# için "geçersiz istek" gibi görünüyordu, web kullanıcıları için ise doğru
# "servis kullanılamıyor" mesajı (cross-platform contract asimetrisi).

def test_service_unavailable_error_code_maps_to_500(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(503, {
        "error": {"code": "SERVICE_UNAVAILABLE", "message": "unavailable"},
    })

    resp = client.post("/api/mobile/auth/refresh", json={"refresh_token": "sometoken"})

    assert resp.status_code == 500
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


# ─── Google Sign-In proxy ─────────────────────────────────────────────────────

def test_google_sign_in_happy_path_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {
        "access_token": "fake-token", "token_type": "bearer", "user_id": 9, "email": "g@test.com",
    })

    resp = client.post("/api/mobile/auth/google", json={"code": "authcode", "redirect_uri": "com.sardogan.TripClipAI:/oauth2redirect"})

    assert resp.status_code == 200
    assert resp.json()["user_id"] == 9


def test_google_sign_in_unverified_email_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": "GOOGLE_EMAIL_NOT_VERIFIED", "message": "unverified"},
    })

    resp = client.post("/api/mobile/auth/google", json={"code": "authcode", "redirect_uri": "com.sardogan.TripClipAI:/oauth2redirect"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "GOOGLE_EMAIL_NOT_VERIFIED"


# ─── Forgot / Reset Password proxy ────────────────────────────────────────────

def test_forgot_password_always_returns_generic_status(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(200, {"status": "ok"})

    resp = client.post("/api/mobile/auth/forgot-password", json={"email": "anything@test.com"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_reset_password_expired_token_passthrough(client, mock_core_api, make_response):
    mock_core_api.post.return_value = make_response(401, {
        "error": {"code": "PASSWORD_RESET_TOKEN_EXPIRED", "message": "expired"},
    })

    resp = client.post("/api/mobile/auth/reset-password", json={"token": "abc", "new_password": "NewSecure123!"})

    assert resp.status_code == 401
    assert resp.json()["code"] == "PASSWORD_RESET_TOKEN_EXPIRED"
