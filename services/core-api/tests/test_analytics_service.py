"""
AnalyticsService testleri: doküman şekli, best-effort davranış, opt-out.
Gerçek Mongo'ya asla bağlanılmaz — MongoAnalyticsClient sahte bir çiftle
enjekte edilir.
"""
from app.application.services.analytics_service import AnalyticsService
from app.core.analytics_events import AnalyticsEvent


class _FakeMongoClient:
    def __init__(self):
        self.recorded = []

    def record(self, document):
        self.recorded.append(document)


def test_track_records_document_with_all_fields():
    mongo = _FakeMongoClient()
    service = AnalyticsService(mongo_client=mongo)

    service.track(
        event=AnalyticsEvent.SHARED_TRIP_LINK_COPIED,
        trip_id=42,
        platform="web",
        user_id=7,
        source="hero_button",
        metadata={"foo": "bar"},
    )

    assert len(mongo.recorded) == 1
    doc = mongo.recorded[0]
    assert doc["event"] == "shared_trip_link_copied"
    assert doc["trip_id"] == 42
    assert doc["platform"] == "web"
    assert doc["user_id"] == 7
    assert doc["source"] == "hero_button"
    assert doc["metadata"] == {"foo": "bar"}
    assert "timestamp" in doc


def test_track_defaults_user_id_to_none_for_anonymous_viewers():
    """Herkese açık bir paylaşım sayfasını gezen, giriş yapmamış biri için
    user_id None olmalı — spesifikasyonun "user_id (when available)" gereksinimi."""
    mongo = _FakeMongoClient()
    service = AnalyticsService(mongo_client=mongo)

    service.track(event=AnalyticsEvent.SHARED_TRIP_OPENED, trip_id=1, platform="web")

    assert mongo.recorded[0]["user_id"] is None
    assert mongo.recorded[0]["source"] is None
    assert mongo.recorded[0]["metadata"] == {}


def test_track_stores_enum_value_not_enum_object():
    """Mongo'ya yazılan değer serileştirilebilir bir string olmalı, Python enum nesnesi değil."""
    mongo = _FakeMongoClient()
    service = AnalyticsService(mongo_client=mongo)

    service.track(event=AnalyticsEvent.SHARED_TRIP_DELETED, trip_id=1, platform="server")

    assert isinstance(mongo.recorded[0]["event"], str)
    assert mongo.recorded[0]["event"] == "shared_trip_deleted"


def test_track_never_raises_when_mongo_client_fails():
    """Best-effort: alt katmandaki bir hata (bağlantı vb.) yukarı sızmamalı —
    çağıran taraf (Celery task, HTTP route) bu çağrının asla patlamayacağına güvenir."""
    class _BoomingMongoClient:
        def record(self, document):
            raise RuntimeError("Mongo unreachable")

    service = AnalyticsService(mongo_client=_BoomingMongoClient())

    # Exception fırlatmamalı.
    service.track(event=AnalyticsEvent.SHARED_TRIP_CREATED, trip_id=1, platform="server")
