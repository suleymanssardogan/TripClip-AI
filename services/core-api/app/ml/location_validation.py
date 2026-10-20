"""Conservative checks for geographic candidates; no external calls."""
import math
import re
import unicodedata
from difflib import SequenceMatcher


def _fold(value):
    value = str(value or "").lower().replace("ı", "i")
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", value)
                              .encode("ascii", "ignore").decode()))


def rejection_reason(query, place, *, bbox=None, city_hint=None, country_code=None):
    """Return an explicit contradiction, or None (not proof of correctness)."""
    if place.get("precision") in {"approximate", "unresolved"}:
        return "unverified_coordinates"
    coords = place.get("location") or {}
    lat, lng = coords.get("lat"), coords.get("lng")
    if (isinstance(lat, bool) or isinstance(lng, bool)
            or not isinstance(lat, (float, int)) or not isinstance(lng, (float, int))
            or not math.isfinite(lat) or not math.isfinite(lng)
            or not -90 <= lat <= 90 or not -180 <= lng <= 180):
        return "invalid_coordinates"
    if bbox and not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lng <= bbox[3]):
        return "outside_region"
    address = place.get("address_details") or {}
    actual_country = address.get("country_code")
    if country_code and actual_country and actual_country.lower() != country_code.lower():
        return "country_conflict"
    name = _fold((place.get("name") or "").split(",")[0])
    expected = _fold(query)
    generic = {"antik", "kenti", "tarihi", "plaji", "koyu", "parki", "muzesi",
               "restoran", "restaurant", "cafe", "kahvesi", "kebap"}
    distinctive = set(expected.split()) - generic
    if name and distinctive and not distinctive.intersection(name.split()):
        if SequenceMatcher(None, expected, name).ratio() < 0.65:
            return "name_conflict"
    # Use structured locality fields only; free-text substrings are not evidence.
    localities = [_fold(address.get(k)) for k in
                  ("city", "town", "municipality", "county", "district", "province", "state")
                  if address.get(k)]
    hint = _fold(city_hint)
    if hint and localities and hint not in localities and hint != name:
        return "locality_conflict"
    return None


def validate_final_candidates(candidates, *, cities=None, regions=None, country_code=None):
    """One final gate after every provider and geographic correction."""
    cities, regions = cities or {}, regions or {}
    accepted, rejected = [], []
    for candidate in candidates:
        name = candidate.get("original_name") or ""
        city = cities.get(name.casefold().strip())
        region = regions.get(city) or {}
        reason = rejection_reason(name, candidate.get("place_data") or {},
                                  bbox=region.get("bbox"), city_hint=city,
                                  country_code=country_code)
        if reason:
            rejected.append({"name": name, "city": city, "status": "unresolved", "reason": reason})
        else:
            accepted.append(candidate)
    return accepted, rejected
