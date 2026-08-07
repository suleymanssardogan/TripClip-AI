"""
Push bildirim testleri: ApnsClient yapılandırma/parsing mantığı ve
PushService'in ne zaman gönderip ne zaman no-op yaptığı — gerçek APNs'e
asla istek atılmaz (ApnsClient sahte bir çift ile enjekte edilir).
"""
from types import SimpleNamespace

from app.infrastructure.push.apns_client import ApnsClient, ApnsResult
from app.application.services.push_service import PushService


# ─── ApnsClient yapılandırma ──────────────────────────────────────────────────

def test_not_configured_when_env_vars_missing(monkeypatch):
    for var in ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_BUNDLE_ID", "APNS_AUTH_KEY"):
        monkeypatch.delenv(var, raising=False)
    client = ApnsClient()
    assert client.is_configured is False


def test_configured_when_all_env_vars_present(monkeypatch):
    monkeypatch.setenv("APNS_KEY_ID", "KEY123")
    monkeypatch.setenv("APNS_TEAM_ID", "TEAM123")
    monkeypatch.setenv("APNS_BUNDLE_ID", "com.tripclip.app")
    monkeypatch.setenv("APNS_AUTH_KEY", "-----BEGIN PRIVATE KEY-----\\nfake\\n-----END PRIVATE KEY-----")
    client = ApnsClient()
    assert client.is_configured is True
    # \\n kaçışları gerçek satır sonuna çevrilmeli (PEM formatı bunu gerektirir)
    assert "\n" in client._auth_key


def test_send_returns_failed_when_not_configured(monkeypatch):
    for var in ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_BUNDLE_ID", "APNS_AUTH_KEY"):
        monkeypatch.delenv(var, raising=False)
    client = ApnsClient()
    result = client.send(device_token="abc", title="t", body="b")
    assert result is ApnsResult.FAILED


def test_sandbox_host_by_default(monkeypatch):
    monkeypatch.delenv("APNS_USE_SANDBOX", raising=False)
    client = ApnsClient()
    assert "sandbox" in client._host


def test_production_host_when_sandbox_disabled(monkeypatch):
    monkeypatch.setenv("APNS_USE_SANDBOX", "false")
    client = ApnsClient()
    assert "sandbox" not in client._host


# ─── PushService — sahte ApnsClient ile ──────────────────────────────────────

class _FakeApns:
    def __init__(self, result=ApnsResult.SENT, configured=True):
        self.is_configured = configured
        self._result = result
        self.calls = []

    def send(self, device_token, title, body, data=None):
        self.calls.append({"device_token": device_token, "title": title, "body": body, "data": data})
        return self._result


class _FakeUserRepo:
    def __init__(self, user=None):
        self._user = user
        self.cleared_for = None

    def get_by_id(self, user_id):
        return self._user

    def clear_apns_token(self, user_id):
        self.cleared_for = user_id


def _video(user_id=1, video_id=42, locations=None):
    return SimpleNamespace(user_id=user_id, id=video_id, deduplicated_locations=locations or [])


def test_notify_completed_sends_push_with_video_id_and_stop_count():
    apns = _FakeApns()
    user = SimpleNamespace(id=1, apns_token="dead-beef")
    repo = _FakeUserRepo(user=user)
    service = PushService(repo, apns_client=apns)

    service.notify_video_completed(_video(video_id=42, locations=[{"a": 1}, {"a": 2}]))

    assert len(apns.calls) == 1
    call = apns.calls[0]
    assert call["device_token"] == "dead-beef"
    assert call["data"] == {"video_id": "42"}
    assert "2" in call["body"]


def test_notify_failed_sends_push():
    apns = _FakeApns()
    user = SimpleNamespace(id=1, apns_token="dead-beef")
    repo = _FakeUserRepo(user=user)
    service = PushService(repo, apns_client=apns)

    service.notify_video_failed(_video())

    assert len(apns.calls) == 1
    assert "işlenemedi" in apns.calls[0]["title"].lower()


def test_no_push_when_video_has_no_owner():
    apns = _FakeApns()
    service = PushService(_FakeUserRepo(), apns_client=apns)

    service.notify_video_completed(_video(user_id=None))

    assert apns.calls == []


def test_no_push_when_apns_not_configured():
    apns = _FakeApns(configured=False)
    user = SimpleNamespace(id=1, apns_token="dead-beef")
    service = PushService(_FakeUserRepo(user=user), apns_client=apns)

    service.notify_video_completed(_video())

    assert apns.calls == []


def test_no_push_when_user_missing():
    apns = _FakeApns()
    service = PushService(_FakeUserRepo(user=None), apns_client=apns)

    service.notify_video_completed(_video())

    assert apns.calls == []


def test_no_push_when_user_has_no_token():
    apns = _FakeApns()
    user = SimpleNamespace(id=1, apns_token=None)
    service = PushService(_FakeUserRepo(user=user), apns_client=apns)

    service.notify_video_completed(_video())

    assert apns.calls == []


def test_invalid_token_result_clears_stored_token():
    apns = _FakeApns(result=ApnsResult.INVALID_TOKEN)
    user = SimpleNamespace(id=7, apns_token="stale-token")
    repo = _FakeUserRepo(user=user)
    service = PushService(repo, apns_client=apns)

    service.notify_video_completed(_video())

    assert repo.cleared_for == 7


def test_failed_result_does_not_clear_token():
    apns = _FakeApns(result=ApnsResult.FAILED)
    user = SimpleNamespace(id=7, apns_token="temp-glitch")
    repo = _FakeUserRepo(user=user)
    service = PushService(repo, apns_client=apns)

    service.notify_video_completed(_video())

    assert repo.cleared_for is None
