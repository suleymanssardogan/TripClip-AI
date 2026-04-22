"""
Auth endpoint testleri: register, login, hata senaryoları
"""
import uuid


# ─── Register ───────────────────────────────────────────────────────────────

def test_register_success(client):
    """Yeni kullanıcı kaydı başarılı olmalı"""
    email = f"new_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/internal/auth/register", json={
        "email": email,
        "password": "Secure123!",
        "username": f"usr_{uuid.uuid4().hex[:6]}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["email"] == email
    assert isinstance(data["user_id"], int)
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client):
    """Aynı e-posta ile iki kez kayıt → 400"""
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    payload = {"email": email, "password": "T3st_pwd!", "username": f"u_{uuid.uuid4().hex[:6]}"}
    r1 = client.post("/internal/auth/register", json=payload)
    assert r1.status_code == 200

    r2 = client.post("/internal/auth/register", json=payload)
    assert r2.status_code == 400
    assert "kayıtlı" in r2.json()["detail"].lower() or "already" in r2.json()["detail"].lower()


def test_register_duplicate_username(client):
    """Aynı kullanıcı adı → 400"""
    username = f"dupuser_{uuid.uuid4().hex[:6]}"
    e1 = f"a_{uuid.uuid4().hex[:6]}@test.com"
    e2 = f"b_{uuid.uuid4().hex[:6]}@test.com"

    r1 = client.post("/internal/auth/register", json={"email": e1, "password": "P1!", "username": username})
    assert r1.status_code == 200

    r2 = client.post("/internal/auth/register", json={"email": e2, "password": "P2!", "username": username})
    assert r2.status_code == 400


def test_register_without_username(client):
    """Kullanıcı adı opsiyonel — e-posta prefix'i kullanılmalı"""
    email = f"nousername_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/internal/auth/register", json={"email": email, "password": "T3st_pwd!"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


# ─── Login ──────────────────────────────────────────────────────────────────

def test_login_success(client, registered_user):
    """Kayıtlı kullanıcı giriş yapabilmeli"""
    resp = client.post("/internal/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["email"] == registered_user["email"]


def test_login_wrong_password(client, registered_user):
    """Yanlış şifre → 401"""
    resp = client.post("/internal/auth/login", json={
        "email": registered_user["email"],
        "password": "WrongPassword999"
    })
    assert resp.status_code == 401


def test_login_nonexistent_email(client):
    """Kayıtlı olmayan e-posta → 401"""
    resp = client.post("/internal/auth/login", json={
        "email": "ghost@nowhere.com",
        "password": "whatever"
    })
    assert resp.status_code == 401


def test_login_missing_fields(client):
    """Eksik alan → 422"""
    resp = client.post("/internal/auth/login", json={"email": "x@x.com"})
    assert resp.status_code == 422
