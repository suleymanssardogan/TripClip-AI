"""
Regression tests for the international-location geocoding bug.

Context: a Budapest travel video was processed and Gemini correctly extracted
"Budapeşte" + "Blueberry Coffee & Brunch", but the final result placed both at
Ankara's coordinates. Root cause was two-fold:
  1. `PlacesService.search_place` hardcoded `countrycodes=tr` on every
     Nominatim query, so non-Turkish places could never geocode at all.
  2. `VideoProcessingService._extract_city_hint` trusted the FIRST
     geocoded entry's city/province, so one bad match (e.g. a BERT-NER
     hallucination) could dictate the whole video's city_hint.

These tests pin both fixes so they can't silently regress.
"""
import unittest.mock as mock

from app.ml.places_service import PlacesService
from app.core.services.video_processor import VideoProcessingService


def _fake_nominatim_response(lat: float, lng: float, city: str, country: str):
    return [{
        "lat": str(lat), "lon": str(lng),
        "display_name": f"{city}, {country}",
        "place_id": 1, "osm_id": 1, "osm_type": "node",
        "type": "city", "class": "place", "importance": 0.8,
        "address": {"city": city, "country": country},
    }]


def test_search_place_has_no_country_restriction_by_default():
    """A non-Turkish place (e.g. Budapest) must be searchable — no hardcoded countrycodes."""
    service = PlacesService()
    service.cache = None  # skip redis

    fake_resp = mock.Mock(status_code=200)
    fake_resp.json.return_value = _fake_nominatim_response(47.4979, 19.0402, "Budapest", "Hungary")

    with mock.patch("app.ml.places_service.requests.get", return_value=fake_resp) as mocked_get:
        result = service.search_place("Budapeşte")

    assert result is not None
    assert result["location"]["lat"] == 47.4979
    called_params = mocked_get.call_args.kwargs["params"]
    assert "countrycodes" not in called_params


def test_search_place_applies_country_restriction_when_requested():
    """Callers that DO know the content is country-specific can still opt in."""
    service = PlacesService()
    service.cache = None

    fake_resp = mock.Mock(status_code=200)
    fake_resp.json.return_value = _fake_nominatim_response(39.9334, 32.8597, "Ankara", "Türkiye")

    with mock.patch("app.ml.places_service.requests.get", return_value=fake_resp) as mocked_get:
        service.search_place("Ankara", country_code="tr")

    called_params = mocked_get.call_args.kwargs["params"]
    assert called_params["countrycodes"] == "tr"


def _enriched(name: str, city: str, place_type: str = "point_of_interest"):
    return {
        "original_name": name,
        "place_data": {
            "name": name,
            "type": place_type,
            "address_details": {"city": city},
        },
    }


def test_extract_city_hint_uses_majority_not_first_entry():
    """
    A single bad geocode (e.g. BERT-NER hallucinating 'Ankara' from a Budapest
    video's transcript) must not override the city agreed on by the other,
    correctly-geocoded entries.
    """
    ner_enriched = [
        _enriched("Hollanda", "Ankara"),               # bad NER-driven false positive, first in list
        _enriched("Budapeşte", "Budapest", "city"),
        _enriched("Blueberry Coffee & Brunch", "Budapest"),
    ]

    city_hint = VideoProcessingService._extract_city_hint(ner_enriched)

    assert city_hint == "Budapest"


def test_extract_city_hint_returns_none_without_votes():
    assert VideoProcessingService._extract_city_hint([]) is None
    assert VideoProcessingService._extract_city_hint(
        [{"original_name": "X", "place_data": {"type": "amenity"}}]
    ) is None
