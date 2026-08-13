"""
Google Sign-In testleri (M34): POST /internal/auth/google.

Gerçek Google API'lerine (kod değişimi + JWKS) hiç bağlanılmaz —
`AuthService._exchange_and_verify_google_code` her zaman mock'lanır (kod
değişimi/imza doğrulamasının kendisi, bu servisin İÇİNDE değil, Google'ın
KENDİ altyapısına ait bir sözleşmedir — burada test edilen, o sözleşimin
DÖNDÜRDÜĞÜ kimlikle AuthService'in ne YAPTIĞIdır: hesap oluşturma/bağlama/
giriş mantığı). `GOOGLE_ALLOWED_REDIRECT_URIS` testler için env'de set edilir.
"""
import uuid
from unittest import mock

import pytest

_REDIRECT_URI = "http://localhost:3000/auth/google/callback"
_VERIFY_TARGET = "app.application.services.auth_service.AuthService._exchange_and_verify_google_code"


@pytest.fixture(autouse=True)
def _allow_redirect_uri(monkeypatch):
    monkeypatch.setenv("GOOGLE_ALLOWED_REDIRECT_URIS", _REDIRECT_URI)


def _google_sign_in(client, google_id, email, email_verified=True, name=None):
    # `name=None` (varsayılan) → AuthService `email.split("@")[0]`'e düşer,
    # bu da her testin KENDİ benzersiz (uuid tabanlı) e-postasından
    # türediği için `username` unique constraint'iyle asla ÇAKIŞMAZ. Sabit
    # bir "Test User" varsayılanı, birden fazla testte/çağrıda AYNI
    # username'i üretip gerçek olmayan bir çakışma yaratırdı.
    with mock.patch(_VERIFY_TARGET, return_value=(google_id, email, email_verified, name)):
        return client.post("/internal/auth/google", json={"code": "fake-auth-code", "redirect_uri": _REDIRECT_URI})


# ─── New identity → new account ─────────────────────────────────────────────

def test_new_google_identity_creates_a_user(client):
    google_id = f"google_{uuid.uuid4().hex[:12]}"
    email = f"newgoogle_{uuid.uuid4().hex[:8]}@test.com"

    resp = _google_sign_in(client, google_id, email)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email
    assert "access_token" in data and "refresh_token" in data


def test_new_google_identity_without_email_is_rejected(client):
    resp = _google_sign_in(client, f"google_{uuid.uuid4().hex[:12]}", email=None)
    assert resp.status_code == 400


# ─── Existing Google identity → sign in to same account ────────────────────

def test_existing_google_identity_signs_into_the_same_account(client):
    google_id = f"google_{uuid.uuid4().hex[:12]}"
    email = f"repeat_{uuid.uuid4().hex[:8]}@test.com"

    first = _google_sign_in(client, google_id, email)
    second = _google_sign_in(client, google_id, email)
    assert first.status_code == second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"]


def test_existing_google_identity_signs_in_even_if_google_now_reports_different_name(client):
    # Google ID (sub) DEĞİŞMEZ kimlik anahtarıdır — isim/e-posta değişse
    # bile AYNI hesaba giriş yapılmalı (bkz. get_by_google_id'nin `email`
    # eşleşmesinden ÖNCE kontrol edilmesi).
    google_id = f"google_{uuid.uuid4().hex[:12]}"
    email = f"stable_{uuid.uuid4().hex[:8]}@test.com"
    first = _google_sign_in(client, google_id, email, name="Original Name")
    second = _google_sign_in(client, google_id, email, name="Updated Name")
    assert first.json()["user_id"] == second.json()["user_id"]


# ─── Account linking — verified email match ─────────────────────────────────

def test_existing_email_password_account_links_on_verified_email_match(client):
    email = f"linkme_{uuid.uuid4().hex[:8]}@test.com"
    register_resp = client.post("/internal/auth/register", json={
        "email": email, "password": "Secure123!", "username": f"usr_{uuid.uuid4().hex[:6]}",
    })
    assert register_resp.status_code == 200
    existing_user_id = register_resp.json()["user_id"]

    google_id = f"google_{uuid.uuid4().hex[:12]}"
    google_resp = _google_sign_in(client, google_id, email, email_verified=True)
    assert google_resp.status_code == 200
    assert google_resp.json()["user_id"] == existing_user_id  # AYNI hesap, yeni bir tane DEĞİL

    # Bağlama kalıcı — bir sonraki Google girişi de AYNI hesaba gider.
    again = _google_sign_in(client, google_id, email, email_verified=True)
    assert again.json()["user_id"] == existing_user_id


def test_password_login_still_works_after_google_account_linking(client):
    # Bağlama, var olan e-posta/şifre giriş yolunu BOZMAMALI.
    email = f"stilllogin_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/internal/auth/register", json={
        "email": email, "password": "Secure123!", "username": f"usr_{uuid.uuid4().hex[:6]}",
    })
    _google_sign_in(client, f"google_{uuid.uuid4().hex[:12]}", email, email_verified=True)

    login_resp = client.post("/internal/auth/login", json={"email": email, "password": "Secure123!"})
    assert login_resp.status_code == 200


# ─── Account linking — unverified email must NOT silently merge ───────────

def test_unverified_email_does_not_link_to_existing_account(client):
    email = f"unverified_{uuid.uuid4().hex[:8]}@test.com"
    register_resp = client.post("/internal/auth/register", json={
        "email": email, "password": "Secure123!", "username": f"usr_{uuid.uuid4().hex[:6]}",
    })
    existing_user_id = register_resp.json()["user_id"]

    resp = _google_sign_in(client, f"google_{uuid.uuid4().hex[:12]}", email, email_verified=False)
    # Ne sessizce BAĞLANIR ne de aynı e-postayla ikinci bir hesap
    # OLUŞTURULMAYA çalışılıp çökertilir — güvenli, açık bir hata.
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "GOOGLE_EMAIL_NOT_VERIFIED"

    # Var olan hesap HİÇ ETKİLENMEDİ — hâlâ normal şekilde giriş yapılabilir.
    login_resp = client.post("/internal/auth/login", json={"email": email, "password": "Secure123!"})
    assert login_resp.status_code == 200
    assert login_resp.json()["user_id"] == existing_user_id


def test_new_google_identity_with_unverified_email_and_no_existing_account_still_creates_user(client):
    # E-posta doğrulanmamış OLABİLİR ama BAŞKA bir hesapla ÇAKIŞMIYORSA
    # (ilk kez görülen bir Google kimliği), hesap yine de oluşturulur —
    # "merge" riski yoktur, yalnızca EŞLEŞTİRME doğrulanmış e-posta
    # gerektirir (bkz. AuthService.google_sign_in'in kendi doc yorumu).
    email = f"freshunverified_{uuid.uuid4().hex[:8]}@test.com"
    resp = _google_sign_in(client, f"google_{uuid.uuid4().hex[:12]}", email, email_verified=False)
    assert resp.status_code == 200


# ─── Redirect URI allowlist ──────────────────────────────────────────────────

def test_redirect_uri_not_in_allowlist_is_rejected(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_ALLOWED_REDIRECT_URIS", "https://legit.example.com/callback")
    with mock.patch(_VERIFY_TARGET, return_value=("g1", "x@test.com", True, "X")):
        resp = client.post("/internal/auth/google", json={
            "code": "fake-code", "redirect_uri": "https://attacker.example.com/callback",
        })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "GOOGLE_AUTH_UNAVAILABLE"
    # Doğrulama isteği Google'a hiç GİTMEDİ — allowlist ihlali erken kesildi.


def test_no_allowed_redirect_uris_configured_disables_google_sign_in(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_ALLOWED_REDIRECT_URIS", raising=False)
    resp = client.post("/internal/auth/google", json={"code": "x", "redirect_uri": _REDIRECT_URI})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "GOOGLE_AUTH_UNAVAILABLE"


# ─── Invalid/expired OAuth credential ───────────────────────────────────────

def test_invalid_or_expired_authorization_code_is_rejected_safely(client):
    from fastapi import HTTPException
    with mock.patch(_VERIFY_TARGET, side_effect=HTTPException(status_code=401, detail="Google authorization code exchange failed")):
        resp = client.post("/internal/auth/google", json={"code": "expired-or-bogus", "redirect_uri": _REDIRECT_URI})
    assert resp.status_code == 401
    assert "Traceback" not in resp.text
    assert "client_secret" not in resp.text.lower()


def test_google_client_not_configured_returns_safe_error(client, monkeypatch):
    # GOOGLE_CLIENT_ID/SECRET boşsa (varsayılan, .env.example) — allowlist
    # doğru ayarlansa bile kod-değişimi denenmeden GÜVENLİ şekilde reddedilir.
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    resp = client.post("/internal/auth/google", json={"code": "x", "redirect_uri": _REDIRECT_URI})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "GOOGLE_AUTH_UNAVAILABLE"


# ─── Rate limiting ────────────────────────────────────────────────────────

def test_google_sign_in_is_rate_limited(client):
    google_id_base = uuid.uuid4().hex[:8]
    for i in range(5):
        resp = _google_sign_in(client, f"google_{google_id_base}_{i}", f"rl{i}_{google_id_base}@test.com")
        assert resp.status_code == 200
    limited = _google_sign_in(client, f"google_{google_id_base}_final", f"rlfinal_{google_id_base}@test.com")
    assert limited.status_code == 429
