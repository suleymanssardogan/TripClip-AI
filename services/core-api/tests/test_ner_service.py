"""
NERService — noise-filtreleme regresyon testleri.

Kök neden (2026-07-25): aggregation_strategy="simple" ardışık aynı-tip
token'ları tek bir entity'de birleştirir ("Ya" + "Allah" → "Ya Allah").
Eski filtre yalnızca tam string eşleşmesi kontrol ediyordu, bu yüzden "ya"
ve "allah" ayrı ayrı noise listesinde olsa bile birleşik "Ya Allah" hiçbir
zaman eşleşmiyordu ve NER bunu gerçek bir konum/işletme sanıp Nominatim'e
gönderiyordu — sonucunda alakasız bir kıtadaki bir yerleşim yeri (Yakutya,
Rusya) "bulunan konum" olarak pipeline'a giriyordu.
"""
from unittest import mock

from app.ml.ner_service import NERService, _is_noise, _LOCATION_NOISE, _ORG_NOISE


# ─── _is_noise — saf fonksiyon testleri ────────────────────────────────────────

def test_is_noise_matches_multiword_interjection_phrase():
    assert _is_noise("Ya Allah", _LOCATION_NOISE) is True
    assert _is_noise("ya allah", _LOCATION_NOISE) is True


def test_is_noise_matches_single_noise_word():
    assert _is_noise("Allah", _LOCATION_NOISE) is True
    assert _is_noise("Ya", _LOCATION_NOISE) is True


def test_is_noise_does_not_match_real_location():
    assert _is_noise("Gaziantep", _LOCATION_NOISE) is False
    assert _is_noise("Kapadokya", _LOCATION_NOISE) is False


def test_is_noise_does_not_match_when_only_part_of_phrase_is_noise():
    # "Ya" noise listesinde ama "Kapadokya" değil — birleşik ifade gerçek
    # bir yer adı içeriyorsa filtrelenmemeli.
    assert _is_noise("Ya Kapadokya", _LOCATION_NOISE) is False


def test_is_noise_org_set_also_catches_location_interjections():
    # Asıl regresyon: "Ya Allah" bazen LOC/GPE değil ORG olarak etiketleniyor
    # (bkz. extract_locations_from_transcript). İlk fix denemesinde _ORG_NOISE
    # "ya" içermiyordu ve bug bu yüzden ORG yolundan sızmaya devam etmişti.
    assert _is_noise("Ya Allah", _ORG_NOISE) is True


def test_is_noise_org_set_does_not_flag_real_business_name():
    assert _is_noise("Kamil Şifa Beyran Salonu", _ORG_NOISE) is False


# ─── extract_entities — uçtan uca (model mock'lanmış) ──────────────────────────

def _make_entity(word, group, score):
    return {"entity_group": group, "score": score, "word": word}


def test_extract_entities_filters_out_bogus_multiword_interjection():
    service = NERService()
    service.model = mock.MagicMock(return_value=[
        _make_entity("Ya Allah", "LOC", 0.90),
        _make_entity("Gaziantep", "LOC", 0.95),
    ])

    results = service.extract_entities("uzun bir transkript metni buraya gelir")

    words = [r["text"] for r in results]
    assert "Ya Allah" not in words
    assert "Gaziantep" in words


def test_extract_locations_from_transcript_filters_org_interjection():
    service = NERService()
    # extract_entities (LOC/GPE) ve ORG taraması aynı model() çağrısını kullanır
    service.model = mock.MagicMock(return_value=[
        _make_entity("Gaziantep", "LOC", 0.95),
        _make_entity("Ya Allah", "ORG", 0.80),
        _make_entity("Kamil Şifa Beyran Salonu", "ORG", 0.85),
    ])

    results = service.extract_locations_from_transcript("uzun bir transkript metni buraya gelir")

    assert "Ya Allah" not in results
    assert "Gaziantep" in results
    assert "Kamil Şifa Beyran Salonu" in results
