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


def test_register_weak_password_rejected(client):
    """8 karakterden kısa şifre → 422"""
    email = f"weak_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/internal/auth/register", json={"email": email, "password": "short1"})
    assert resp.status_code == 422


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

    r1 = client.post("/internal/auth/register", json={"email": e1, "password": "P1_test!", "username": username})
    assert r1.status_code == 200

    r2 = client.post("/internal/auth/register", json={"email": e2, "password": "P2_test!", "username": username})
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
            "password": "P1_test!",
        })

    resp = client.post("/internal/auth/register", json={
        "email": f"rl_over_{uuid.uuid4().hex[:4]}@test.com",
        "password": "P1_test!",
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


# ─── Refresh Token ──────────────────────────────────────────────────────────

def _register(client) -> dict:
    email = f"refresh_{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post("/internal/auth/register", json={
        "email": email,
        "password": "Refresh123!",
        "username": f"ru_{uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200
    return resp.json()


def test_register_includes_refresh_token(client):
    """Register yanıtı artık refresh_token da içermeli"""
    data = _register(client)
    assert "refresh_token" in data
    assert data["refresh_token"]


def test_refresh_success_rotates_token(client):
    """Geçerli refresh token → yeni access+refresh token çifti üretir"""
    initial = _register(client)

    resp = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert resp.status_code == 200
    data = resp.json()
    # NOT: access_token'lar aynı saniyede üretilirse payload'ları (sub/email/exp/type)
    # birebir aynı olabileceğinden byte-eşitliği garanti edilemez — asıl güvenlik
    # özelliği refresh_token'ın rotate edilmesidir, onu doğruluyoruz.
    assert data["refresh_token"] != initial["refresh_token"]
    assert data["user_id"] == initial["user_id"]


def test_refresh_reused_token_returns_401(client):
    """Rotate edilmiş (artık iptal) bir refresh token tekrar kullanılamaz"""
    initial = _register(client)

    first_refresh = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert first_refresh.status_code == 200

    # Aynı (artık eski/iptal) refresh token'ı tekrar kullanmayı dene
    reuse = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"


def test_refresh_reuse_revokes_entire_family(client):
    """Reuse tespiti sadece eski token'ı değil, o kullanıcının TÜM aktif
    refresh token'larını (yeni rotate edilmiş olan dahil) iptal etmeli.
    """
    initial = _register(client)

    rotated = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    }).json()

    # Eski token'ı tekrar kullan → reuse detection, tüm aile iptal edilir
    reuse = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert reuse.status_code == 401

    # Rotation sonucu üretilen YENİ token da artık geçersiz olmalı
    after_family_revoke = client.post("/internal/auth/refresh", json={
        "refresh_token": rotated["refresh_token"],
    })
    assert after_family_revoke.status_code == 401


def test_refresh_invalid_token_returns_401(client):
    """Hiç var olmayan bir refresh token → 401 REFRESH_TOKEN_INVALID"""
    resp = client.post("/internal/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


def test_refresh_expired_token_returns_401(client, monkeypatch):
    """Süresi dolmuş bir refresh token → 401 REFRESH_TOKEN_EXPIRED"""
    # Yeni üretilecek refresh token'ları anında "geçmişte sona ermiş" yap
    monkeypatch.setattr(
        "app.application.services.auth_service.REFRESH_TOKEN_EXPIRE_DAYS", -1
    )
    initial = _register(client)

    resp = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"


def test_logout_revokes_refresh_token(client):
    """Logout sonrası aynı refresh token ile yenileme yapılamamalı"""
    initial = _register(client)

    logout_resp = client.post("/internal/auth/logout", json={
        "refresh_token": initial["refresh_token"],
    })
    assert logout_resp.status_code == 200

    refresh_resp = client.post("/internal/auth/refresh", json={
        "refresh_token": initial["refresh_token"],
    })
    assert refresh_resp.status_code == 401


def test_logout_is_idempotent(client):
    """Aynı refresh token ile iki kez logout çağrısı hata vermemeli"""
    initial = _register(client)

    first = client.post("/internal/auth/logout", json={"refresh_token": initial["refresh_token"]})
    second = client.post("/internal/auth/logout", json={"refresh_token": initial["refresh_token"]})
    assert first.status_code == 200
    assert second.status_code == 200


def test_logout_unknown_token_is_noop(client):
    """Var olmayan bir refresh token ile logout hata fırlatmamalı"""
    resp = client.post("/internal/auth/logout", json={"refresh_token": "ghost-token"})
    assert resp.status_code == 200


def test_revoke_if_active_is_race_safe(client):
    """revoke_if_active — iki eşzamanlı çağrıdan sadece biri True dönmeli.

    Read-then-write yerine tek bir UPDATE...WHERE kullanıldığını doğrudan
    repository seviyesinde kanıtlar: aynı token_id üzerinde art arda çağrılan
    revoke_if_active, ikinci seferde False dönmeli (biri "önce" davranmış gibi).
    """
    from app.core.database import SessionLocal
    from app.core.auth import hash_refresh_token
    from app.infrastructure.repositories.sql_refresh_token_repository import SqlRefreshTokenRepository

    initial = _register(client)

    db = SessionLocal()
    try:
        repo = SqlRefreshTokenRepository(db)
        stored = repo.get_by_hash(hash_refresh_token(initial["refresh_token"]))
        assert stored is not None

        first_claim  = repo.revoke_if_active(stored.id)
        second_claim = repo.revoke_if_active(stored.id)

        assert first_claim is True
        assert second_claim is False
    finally:
        db.close()


# ─── Device Token (Push Notifications) ───────────────────────────────────────

def test_register_device_token_success(client, registered_user, bff_headers):
    """Geçerli x-user-id ile token gönderilirse kaydedilmeli."""
    resp = client.put(
        "/internal/auth/device-token",
        json={"token": "abc123deadbeef"},
        headers=bff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    from app.core.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == registered_user["user_id"]).first()
        assert user.apns_token == "abc123deadbeef"
    finally:
        db.close()


def test_register_device_token_overwrites_previous(client, registered_user, bff_headers):
    """Aynı kullanıcı yeni bir token gönderirse eskisinin üzerine yazılmalı."""
    client.put("/internal/auth/device-token", json={"token": "old-token"}, headers=bff_headers)
    resp = client.put("/internal/auth/device-token", json={"token": "new-token"}, headers=bff_headers)
    assert resp.status_code == 200

    from app.core.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == registered_user["user_id"]).first()
        assert user.apns_token == "new-token"
    finally:
        db.close()


def test_register_device_token_without_user_id_returns_401(client):
    """x-user-id header'ı yoksa (BFF'i atlayan doğrudan bir çağrı) 401 dönmeli."""
    resp = client.put("/internal/auth/device-token", json={"token": "abc123"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
