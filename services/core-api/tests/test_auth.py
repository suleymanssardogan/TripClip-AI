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
    body = r2.json()
    # Global error handler → {"error": {"code": ..., "message": ...}}
    assert body["error"]["code"] == "DUPLICATE_EMAIL"
    assert "kayıtlı" in body["error"]["message"].lower()


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


# ─── Rate Limiting ──────────────────────────────────────────────────────────

def test_login_rate_limit(client):
    """Login endpoint 5/dakika limiti — 6. istekte 429 dönmeli"""
    payload = {"email": "brute@attacker.com", "password": "wrong"}
    # First 5 requests: 401 (wrong credentials but within rate limit)
    for i in range(5):
        r = client.post("/internal/auth/login", json=payload)
        assert r.status_code == 401, f"Beklenen 401, {i+1}. istekte {r.status_code} geldi"

    # 6th request: 429 Too Many Requests
    resp = client.post("/internal/auth/login", json=payload)
    assert resp.status_code == 429, f"6. istekte 429 beklendi, {resp.status_code} geldi"


def test_register_rate_limit(client):
    """Register endpoint 10/dakika limiti — 11. istekte 429 dönmeli"""
    for i in range(10):
        client.post("/internal/auth/register", json={
            "email": f"rl_{i}_{uuid.uuid4().hex[:4]}@test.com",
            "password": "P1!",
        })

    resp = client.post("/internal/auth/register", json={
        "email": f"rl_over_{uuid.uuid4().hex[:4]}@test.com",
        "password": "P1!",
    })
    assert resp.status_code == 429, f"11. istekte 429 beklendi, {resp.status_code} geldi"


def test_rate_limit_response_format(client):
    """429 yanıtı standart JSON formatında dönmeli"""
    payload = {"email": "brute2@attacker.com", "password": "wrong"}
    for _ in range(5):
        client.post("/internal/auth/login", json=payload)

    resp = client.post("/internal/auth/login", json=payload)
    assert resp.status_code == 429
    # slowapi'nin varsayılan yanıtı ya "error" ya da "message" içerir
    body = resp.json()
    assert isinstance(body, dict), "429 yanıtı JSON dict olmalı"


def test_login_rate_limit_resets_between_tests(client, registered_user):
    """Her test reset_rate_limiters fixture'ı sayesinde temiz başlar.

    Önceki rate limit testleri bu testi etkilememeli.
    """
    resp = client.post("/internal/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200, (
        "Rate limiter sıfırlanmadı — önceki testlerden sayaç taşıyor."
    )
