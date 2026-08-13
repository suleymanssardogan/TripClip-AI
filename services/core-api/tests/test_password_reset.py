"""
Şifre sıfırlama testleri (M34): /internal/auth/forgot-password + /reset-password.

Gerçek SMTP sunucusuna hiç bağlanılmaz — `EmailService.send` her zaman
mock'lanır; testler ham sıfırlama linkini/token'ını gönderilen e-posta
GÖVDESİNDEN (mock'un yakaladığı `body` argümanından) çıkarır — tıpkı gerçek
bir kullanıcının e-postasındaki linke tıklaması gibi.
"""
import re
import uuid
from unittest import mock

import pytest


def _register(client, password="Secure123!") -> dict:
    email = f"reset_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/internal/auth/register", json={
        "email": email, "password": password, "username": f"usr_{uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200
    data = resp.json()
    data["email"] = email
    data["password"] = password
    return data


def _request_reset_and_capture_token(client, email: str) -> str:
    """Gerçek /forgot-password route'unu çağırır, `EmailService.send`'i
    mock'layıp gövdeden ham token'ı çıkarır — testin GERÇEK route/service/
    repository zincirini uçtan uca kullanmasını sağlar, yalnızca dış SMTP
    çağrısı sahtedir."""
    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True) as mock_send:
        resp = client.post("/internal/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert mock_send.called
    _, kwargs = mock_send.call_args
    match = re.search(r"token=([\w-]+)", kwargs["body"])
    assert match, "e-posta gövdesinde bir sıfırlama token'ı bulunamadı"
    return match.group(1)


# ─── Forgot password — enumeration resistance ───────────────────────────────

def test_forgot_password_existing_email_returns_generic_success(client):
    user = _register(client)
    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True):
        resp = client.post("/internal/auth/forgot-password", json={"email": user["email"]})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_forgot_password_unknown_email_returns_the_same_generic_success(client):
    resp = client.post("/internal/auth/forgot-password", json={"email": "nobody-here@test.com"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_forgot_password_malformed_email_still_returns_generic_success(client):
    # Kasıtlı olarak biçim doğrulaması YAPILMAZ — bir "geçersiz e-posta
    # formatı" hatası bile dolaylı bir enumeration sinyali olurdu.
    resp = client.post("/internal/auth/forgot-password", json={"email": "not-an-email-at-all"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_forgot_password_existing_and_unknown_email_produce_identical_responses(client):
    """Enumeration direnci — var olan/olmayan hesap için status_code VE
    gövde BİREBİR aynı olmalı, hiçbir alandan ayırt edilememeli."""
    user = _register(client)
    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True):
        resp_existing = client.post("/internal/auth/forgot-password", json={"email": user["email"]})
    resp_unknown = client.post("/internal/auth/forgot-password", json={"email": "definitely-not-registered@test.com"})

    assert resp_existing.status_code == resp_unknown.status_code == 200
    assert resp_existing.json() == resp_unknown.json()


def test_forgot_password_social_only_account_returns_generic_success_no_email_sent(client):
    # Şifresiz (yalnızca sosyal giriş) bir hesap için de AYNI genel yanıt —
    # ayrıca gerçekten e-posta göndermeye ÇALIŞILMADIĞI da doğrulanır
    # (sıfırlanacak bir şifresi yok, bkz. AuthService.request_password_reset).
    # Doğrudan repository ile şifresiz bir kullanıcı oluşturulur (Apple/Google
    # akışını taklit eder, gerçek OAuth'a gerek kalmadan).
    from app.core.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        social_email = f"social_{uuid.uuid4().hex[:8]}@test.com"
        db.add(User(email=social_email, username=f"social_{uuid.uuid4().hex[:6]}",
                     hashed_password=None, apple_id=f"apple_{uuid.uuid4().hex[:8]}"))
        db.commit()
    finally:
        db.close()

    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True) as mock_send:
        resp = client.post("/internal/auth/forgot-password", json={"email": social_email})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_send.assert_not_called()


def test_forgot_password_never_leaks_the_raw_token_in_the_response(client):
    user = _register(client)
    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True) as mock_send:
        resp = client.post("/internal/auth/forgot-password", json={"email": user["email"]})
    assert resp.json() == {"status": "ok"}
    # Yanıt SADECE {"status": "ok"} — token'a dair hiçbir alan yok.
    assert "token" not in resp.text.lower() or "status" == list(resp.json().keys())[0]
    _, kwargs = mock_send.call_args
    raw_token = re.search(r"token=([\w-]+)", kwargs["body"]).group(1)
    assert raw_token not in resp.text  # ham token yanıtta YOK


def test_forgot_password_requesting_again_invalidates_the_previous_token(client):
    user = _register(client)
    first_token = _request_reset_and_capture_token(client, user["email"])
    second_token = _request_reset_and_capture_token(client, user["email"])
    assert first_token != second_token

    # Eski (birinci) token artık KULLANILAMAZ.
    resp = client.post("/internal/auth/reset-password", json={
        "token": first_token, "new_password": "BrandNewPass123!",
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "PASSWORD_RESET_TOKEN_USED"

    # Yeni (ikinci) token hâlâ ÇALIŞIR.
    resp2 = client.post("/internal/auth/reset-password", json={
        "token": second_token, "new_password": "BrandNewPass123!",
    })
    assert resp2.status_code == 200


# ─── Reset password — token validity ────────────────────────────────────────

def test_reset_password_with_invalid_token(client):
    resp = client.post("/internal/auth/reset-password", json={
        "token": "this-token-was-never-issued", "new_password": "BrandNewPass123!",
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "PASSWORD_RESET_TOKEN_INVALID"


def test_reset_password_with_expired_token(client, monkeypatch):
    monkeypatch.setattr("app.application.services.auth_service.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", -1)
    user = _register(client)
    token = _request_reset_and_capture_token(client, user["email"])

    resp = client.post("/internal/auth/reset-password", json={
        "token": token, "new_password": "BrandNewPass123!",
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "PASSWORD_RESET_TOKEN_EXPIRED"


def test_reset_password_reused_token_is_rejected(client):
    user = _register(client)
    token = _request_reset_and_capture_token(client, user["email"])

    first = client.post("/internal/auth/reset-password", json={
        "token": token, "new_password": "BrandNewPass123!",
    })
    assert first.status_code == 200

    reuse = client.post("/internal/auth/reset-password", json={
        "token": token, "new_password": "AnotherPass456!",
    })
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "PASSWORD_RESET_TOKEN_USED"


def test_reset_password_weak_new_password_rejected(client):
    user = _register(client)
    token = _request_reset_and_capture_token(client, user["email"])

    resp = client.post("/internal/auth/reset-password", json={"token": token, "new_password": "short"})
    assert resp.status_code == 422  # pydantic doğrulama hatası, servise hiç ULAŞMAZ


# ─── Reset password — success path ──────────────────────────────────────────

def test_reset_password_success_then_login_with_new_password(client):
    user = _register(client, password="OldPassword123!")
    token = _request_reset_and_capture_token(client, user["email"])

    resp = client.post("/internal/auth/reset-password", json={
        "token": token, "new_password": "NewPassword456!",
    })
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    login_resp = client.post("/internal/auth/login", json={
        "email": user["email"], "password": "NewPassword456!",
    })
    assert login_resp.status_code == 200


def test_old_password_rejected_after_reset(client):
    user = _register(client, password="OldPassword123!")
    token = _request_reset_and_capture_token(client, user["email"])
    client.post("/internal/auth/reset-password", json={"token": token, "new_password": "NewPassword456!"})

    old_login = client.post("/internal/auth/login", json={
        "email": user["email"], "password": "OldPassword123!",
    })
    assert old_login.status_code == 401


def test_reset_password_revokes_existing_refresh_tokens(client):
    """Şifre sıfırlandıktan sonra, sıfırlama ÖNCESİNDE alınmış bir refresh
    token'la yenileme yapılamamalı — hesabın ele geçirilmiş olma ihtimaline
    karşı standart güvenlik pratiği (bkz. AuthService.reset_password'ın
    kendi doc yorumu)."""
    user = _register(client, password="OldPassword123!")
    old_refresh_token = user["refresh_token"]

    token = _request_reset_and_capture_token(client, user["email"])
    client.post("/internal/auth/reset-password", json={"token": token, "new_password": "NewPassword456!"})

    refresh_resp = client.post("/internal/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_resp.status_code == 401


def test_reset_password_revokes_sessions_even_if_password_update_fails(client, monkeypatch):
    """M39 audit bulgusu: `AuthService.reset_password` artık
    `revoke_all_for_user`'ı `update_password`'DAN ÖNCE çağırıyor — ikisi
    ayrı commit'ler olduğu için aralarında bir hata/çökme olursa sonucun
    "şifre değişti ama eski oturumlar hâlâ geçerli" (bu metodun asıl
    güvenlik amacını baltalayan bir durum) yerine "oturumlar iptal edildi
    ama şifre değişmedi, kullanıcı tekrar dener" tarafında kalmasını
    garantiler. Burada `update_password`'ın KENDİSİ hata fırlatacak şekilde
    monkeypatch'lenir; eski refresh token'ın YİNE DE artık geçersiz olduğu
    doğrulanır."""
    user = _register(client, password="OldPassword123!")
    old_refresh_token = user["refresh_token"]
    token = _request_reset_and_capture_token(client, user["email"])

    def _boom(self, user_id, hashed_password):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(
        "app.infrastructure.repositories.sql_user_repository.SqlUserRepository.update_password",
        _boom,
    )

    resp = client.post("/internal/auth/reset-password", json={
        "token": token, "new_password": "NewPassword456!",
    })
    assert resp.status_code >= 500

    # Şifre GÜNCELLENMEDİ — eski şifreyle giriş hâlâ çalışır.
    login_resp = client.post("/internal/auth/login", json={
        "email": user["email"], "password": "OldPassword123!",
    })
    assert login_resp.status_code == 200

    # ...ama eski oturum YİNE DE iptal edildi — çökme güvenli tarafta oldu.
    refresh_resp = client.post("/internal/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_resp.status_code == 401


# ─── Rate limiting (existing convention: sensitive auth ops) ────────────────

def test_forgot_password_is_rate_limited(client):
    with mock.patch("app.infrastructure.email.email_service.EmailService.send", return_value=True):
        for i in range(5):
            resp = client.post("/internal/auth/forgot-password", json={"email": f"probe{i}@test.com"})
            assert resp.status_code == 200
        limited = client.post("/internal/auth/forgot-password", json={"email": "probe-final@test.com"})
    assert limited.status_code == 429
