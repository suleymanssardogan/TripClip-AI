"""
Sağlık kontrol testleri
"""


def test_health_check(client):
    """GET /health → 200 + healthy"""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "core-api"


def test_root_redirect(client):
    """GET / → 200 veya redirect"""
    resp = client.get("/", follow_redirects=True)
    assert resp.status_code in (200, 404)  # docs veya 404 kabul
