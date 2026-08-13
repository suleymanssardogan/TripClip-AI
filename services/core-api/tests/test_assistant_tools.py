"""
Trip Assistant salt-okunur araçları (M32) birim testleri — saf fonksiyonlar,
DB/HTTP YOK. `app/domain/assistant/tools.py`.
"""
from app.domain.assistant.context_builder import ContextDay, ContextStop, TripContext
from app.domain.assistant.tools import (
    TOOL_DEFINITIONS,
    TOOL_NAMES,
    ToolCallRequest,
    execute_tool,
)


def _context(days=None):
    return TripContext(
        trip_id=2, title="Gaziantep Gezisi", today="2026-08-11",
        has_applied_itinerary=False, itinerary_applied_at=None,
        days=days or [],
    )


def _two_day_context():
    return _context(days=[
        ContextDay(day_index=0, date="2026-08-08", stops=[
            ContextStop(place_id=25, name="Antep", order_index=0, city="Gaziantep",
                        arrival_time="09:00", departure_time="10:00", visit_duration_minutes=60),
            ContextStop(place_id=26, name="Zeugma Müzesi", order_index=1, city="Gaziantep"),
        ]),
        ContextDay(day_index=1, date="2026-08-09", stops=[
            ContextStop(place_id=27, name="Kale", order_index=0, city="Gaziantep"),
        ]),
    ])


# ─── Tool registry ────────────────────────────────────────────────────────

def test_all_expected_tools_are_registered():
    assert TOOL_NAMES == {"get_trip_day", "find_trip_stop"}


def test_tool_definitions_have_stable_names_and_descriptions():
    names = [t.name for t in TOOL_DEFINITIONS]
    assert names == ["get_trip_day", "find_trip_stop"]
    assert all(t.description for t in TOOL_DEFINITIONS)


def test_unknown_tool_is_rejected_safely_not_a_crash():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="delete_trip"))
    assert "error" in result
    assert "delete_trip" in result["error"]


# ─── get_trip_day ────────────────────────────────────────────────────────

def test_get_trip_day_returns_stops_for_the_requested_day():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="get_trip_day", day_index=0))
    assert result["day_index"] == 0
    assert result["date"] == "2026-08-08"
    assert [s["place_id"] for s in result["stops"]] == [25, 26]
    assert result["stops"][0]["arrival_time"] == "09:00"


def test_get_trip_day_second_day_returns_only_its_own_stops():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="get_trip_day", day_index=1))
    assert [s["place_id"] for s in result["stops"]] == [27]


def test_get_trip_day_missing_day_index_returns_safe_error():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="get_trip_day", day_index=None))
    assert "error" in result


def test_get_trip_day_nonexistent_day_returns_safe_error_not_crash():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="get_trip_day", day_index=99))
    assert "error" in result
    assert "99" in result["error"]


def test_get_trip_day_on_empty_trip_returns_safe_error():
    context = _context(days=[])
    result = execute_tool(context, ToolCallRequest(name="get_trip_day", day_index=0))
    assert "error" in result


# ─── find_trip_stop ──────────────────────────────────────────────────────

def test_find_trip_stop_returns_matching_stop_and_day():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="find_trip_stop", place_id=27))
    assert result["day_index"] == 1
    assert result["date"] == "2026-08-09"
    assert result["stop"]["place_id"] == 27
    assert result["stop"]["name"] == "Kale"


def test_find_trip_stop_missing_place_id_returns_safe_error():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="find_trip_stop", place_id=None))
    assert "error" in result


def test_find_trip_stop_nonexistent_place_returns_safe_error_not_crash():
    context = _two_day_context()
    result = execute_tool(context, ToolCallRequest(name="find_trip_stop", place_id=999))
    assert "error" in result
    assert "999" in result["error"]


# ─── Security boundary ───────────────────────────────────────────────────
# Milestone Req 4: araç fonksiyonlarının imzasında trip_id/user_id YOK —
# yalnızca ZATEN yetkilendirilmiş `TripContext`'in kendisi üzerinde çalışır.
# Bu testler, farklı bir context enjekte edildiğinde aracın YALNIZCA O
# context'i gördüğünü kanıtlar (model "başka bir trip" diye bir şey
# SEÇEMEZ — bkz. ToolCallRequest'in kendi alanları).

def test_tool_call_request_has_no_trip_or_user_id_field():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(ToolCallRequest)}
    assert fields == {"name", "day_index", "place_id"}


def test_find_trip_stop_only_ever_searches_the_injected_context():
    context_a = _context(days=[ContextDay(day_index=0, date=None, stops=[
        ContextStop(place_id=1, name="A'nın mekanı", order_index=0),
    ])])
    context_b = _context(days=[ContextDay(day_index=0, date=None, stops=[
        ContextStop(place_id=1, name="B'nin mekanı", order_index=0),
    ])])
    # AYNI place_id (1), FARKLI context — sonuç yalnızca kendi context'ine
    # göre değişmeli, "hangi trip" diye ayrı bir seçim YOK.
    result_a = execute_tool(context_a, ToolCallRequest(name="find_trip_stop", place_id=1))
    result_b = execute_tool(context_b, ToolCallRequest(name="find_trip_stop", place_id=1))
    assert result_a["stop"]["name"] == "A'nın mekanı"
    assert result_b["stop"]["name"] == "B'nin mekanı"
