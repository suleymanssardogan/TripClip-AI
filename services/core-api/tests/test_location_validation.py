import pytest
from app.ml.location_validation import rejection_reason


def place(name="Efes Antik Kenti", **extra):
    return {"name": name, "location": {"lat": 37.94, "lng": 27.34}, **extra}


def test_efes_in_urla_is_rejected_even_inside_broad_izmir_bounds():
    candidate = place(address_details={"town": "Urla", "province": "İzmir"})
    assert rejection_reason("Efes Antik Kenti", candidate, bbox=(37, 26, 39, 28),
                            city_hint="Selçuk") == "locality_conflict"


def test_efes_selcuk_and_turkish_spelling_are_accepted():
    candidate = place("Efes Antik Kenti, Selçuk", address_details={"town": "Selçuk", "country_code": "tr"})
    assert rejection_reason("Efes Antik Kenti", candidate, city_hint="Selcuk", country_code="TR") is None


@pytest.mark.parametrize("coords", [{}, {"lat": float("nan"), "lng": 27},
                                   {"lat": 91, "lng": 27}, {"lat": True, "lng": 27}])
def test_invalid_coordinates_never_become_stops(coords):
    assert rejection_reason("Efes", place(location=coords)) == "invalid_coordinates"


def test_wrong_landmark_name_is_rejected():
    assert rejection_reason("Efes Antik Kenti", place("Urla")) == "name_conflict"


def test_region_and_country_conflicts():
    assert rejection_reason("Efes", place(), bbox=(38, 26, 39, 28)) == "outside_region"
    assert rejection_reason("Efes", place(address_details={"country_code": "gr"}), country_code="tr") == "country_conflict"


def test_absent_locality_is_not_invented():
    assert rejection_reason("Efes Antik Kenti", place(), city_hint="Selçuk") is None


def test_enrichment_filters_conflicting_provider_result_before_returning():
    from unittest.mock import Mock
    from app.ml.places_service import PlacesService
    service = PlacesService.__new__(PlacesService)
    service.search_place = Mock(return_value=place(
        importance=0.5, **{"class": "historic", "type": "ruins"},
        address_details={"town": "Urla", "province": "İzmir"}))
    service._restore_ocr_turkish = Mock(return_value=None)
    assert service.enrich_locations(
        ["Efes Antik Kenti"], city_bbox=(37, 26, 39, 28), city_hint="Selçuk") == []


@pytest.mark.parametrize('source', ['ner', 'ocr', 'vision', 'outlier_replacement'])
def test_final_gate_rejects_bad_coordinates_from_every_origin(source):
    from app.ml.location_validation import validate_final_candidates
    candidate = {'original_name': 'Efes', 'place_data': place('Efes',
        source=source, location={'lat': 91, 'lng': 27})}
    accepted, rejected = validate_final_candidates([candidate])
    assert accepted == []
    assert rejected[0]['reason'] == 'invalid_coordinates'


def test_final_gate_preserves_each_places_own_region():
    from app.ml.location_validation import validate_final_candidates
    candidates = [
        {'original_name': 'Efes', 'place_data': place('Efes', address_details={'town': 'Selçuk'})},
        {'original_name': 'Urla', 'place_data': place('Urla', location={'lat': 38.32, 'lng': 26.76},
                                                   address_details={'town': 'Urla'})},
    ]
    accepted, rejected = validate_final_candidates(candidates,
        cities={'efes': 'Selçuk', 'urla': 'Urla'}, regions={
            'Selçuk': {'bbox': (37.9, 27.3, 38.0, 27.4)},
            'Urla': {'bbox': (38.3, 26.7, 38.4, 26.8)},
        })
    assert len(accepted) == 2 and rejected == []
