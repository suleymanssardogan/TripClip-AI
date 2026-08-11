"""
Overnight Time Ranges milestone — paylaşılan zaman-penceresi yardımcıları
(`greedy_distance_strategy.py`'de yaşar, `ortools_strategy.py` buradan
import eder) doğrudan, herhangi bir stratejiden bağımsız test edilir.
Strateji-spesifik davranış (greedy'nin "yumuşak" zamanlaması, OR-Tools'un
sert kısıtları) sırasıyla test_optimization_strategy.py/
test_ortools_strategy.py'de; iki stratejinin AYNI pencereyi aynı şekilde
yorumladığının kanıtı test_strategy_comparison.py'de.
"""
import pytest

from app.infrastructure.optimization.greedy_distance_strategy import (
    MINUTES_PER_DAY,
    PlanningTimeWindow,
    _parse_opening_hours,
    _day_budget,
    _day_relative_window,
    _window_overlaps_day,
    _resolve_arrival,
)


# ─── _parse_opening_hours: parser ────────────────────────────────────────────

def test_parse_opening_hours_normal_window():
    assert _parse_opening_hours("09:00-18:00") == (540, 1080)


def test_parse_opening_hours_overnight_window():
    """Ayrıştırma, HAM (open > close) çifti reddetmeden döner — overnight
    yorumlama burada DEĞİL, `_day_relative_window`/`_resolve_arrival`'da."""
    assert _parse_opening_hours("22:00-02:00") == (1320, 120)


def test_parse_opening_hours_malformed_returns_none_safely():
    """Yalnızca YAPISAL olarak ayrıştırılamayan (bir '-' ile ayrılmış iki
    'HH:MM' değeri olmayan) girdi None döner — saat/dakika ARALIK doğrulaması
    (`0-23`/`0-59`) bu fonksiyonun sorumluluğu DEĞİL, bu milestone ÖNCESİNDE
    de yoktu ve buradaki 'malformed' Req 6'sının kapsamı (yapısal olarak
    reddedilemeyen bir yer meta verisi, kullanıcı girdisi DEĞİL — bkz.
    `OptimizationService._validate_hhmm`'in AYRI, kullanıcı-girdisi-özel
    aralık kontrolü)."""
    assert _parse_opening_hours("not-a-window") is None
    assert _parse_opening_hours("09:00") is None
    assert _parse_opening_hours("") is None


def test_parse_opening_hours_missing_returns_none():
    assert _parse_opening_hours(None) is None


def test_parse_opening_hours_equal_start_and_end_parses_fine():
    """Ayrıştırma seviyesinde eşit start/end reddedilmez — dejenere
    ("her zaman kapalı") anlamı `_resolve_arrival` seviyesinde ortaya
    çıkar (bkz. aşağıdaki test_resolve_arrival_equal_open_close_always_conflicts)."""
    assert _parse_opening_hours("12:00-12:00") == (720, 720)


# ─── PlanningTimeWindow.parse ────────────────────────────────────────────────

def test_planning_time_window_same_day_range():
    window = PlanningTimeWindow.parse("09:00", "18:00")
    assert window.start_minutes == 540
    assert window.end_minutes == 1080
    assert window.is_overnight is False
    assert window.duration_minutes == 540


def test_planning_time_window_overnight_range():
    window = PlanningTimeWindow.parse("18:00", "01:00")
    assert window.start_minutes == 1080
    assert window.end_minutes == 1500  # 60 + MINUTES_PER_DAY, SÜREKLİ
    assert window.is_overnight is True
    assert window.duration_minutes == 420  # 7 saat


def test_planning_time_window_far_overnight_range():
    window = PlanningTimeWindow.parse("23:30", "03:00")
    assert window.is_overnight is True
    assert window.duration_minutes == 210  # 3.5 saat


def test_planning_time_window_equal_start_and_end_raises():
    with pytest.raises(ValueError):
        PlanningTimeWindow.parse("12:00", "12:00")


def test_planning_time_window_malformed_raises():
    with pytest.raises(ValueError):
        PlanningTimeWindow.parse("not-a-time", "18:00")


# ─── _day_budget ──────────────────────────────────────────────────────────────

def test_day_budget_same_day():
    assert _day_budget(540, 1080) == 540


def test_day_budget_overnight_raw_end():
    # day_end HAM (henüz uzatılmamış, ör. doğrudan _parse_hhmm çıktısı).
    assert _day_budget(1080, 60) == 420


def test_day_budget_overnight_already_extended_end_is_idempotent():
    # day_end ZATEN uzatılmış (PlanningTimeWindow.parse çıktısı gibi) —
    # aynı sonucu vermeli (bkz. modül docstring "idempotent").
    assert _day_budget(1080, 1500) == 420


# ─── _day_relative_window ────────────────────────────────────────────────────

def test_day_relative_window_already_open_when_day_starts_clips_to_zero():
    """Mevcut (bu milestone ÖNCESİ) davranışla BİREBİR aynı sonuç: mekan
    gün başlamadan önce zaten açıksa rel_open = 0."""
    rel_open, rel_close = _day_relative_window(540, 1080, 720)  # 09-18 açık, gün 12:00'da başlıyor
    assert (rel_open, rel_close) == (0, 360)


def test_day_relative_window_opens_later_today():
    rel_open, rel_close = _day_relative_window(1140, 1380, 1080)  # 19:00-23:00, gün 18:00'da başlıyor
    assert (rel_open, rel_close) == (60, 300)


def test_day_relative_window_overnight_place_window():
    rel_open, rel_close = _day_relative_window(1320, 120, 1080)  # 22:00-02:00, gün 18:00'da başlıyor
    assert (rel_open, rel_close) == (240, 480)


def test_day_relative_window_already_closed_today_rolls_to_tomorrow():
    """Case C: gün geç başlıyor (18:00), mekan ERKEN bir pencereye sahip
    (00:00-04:00) — bugünün penceresi zaten geçti, YARININ (ertesi takvim
    günü) penceresi kullanılmalı."""
    rel_open, rel_close = _day_relative_window(0, 240, 1080)
    assert (rel_open, rel_close) == (360, 600)


def test_day_relative_window_always_monotonic():
    """rel_close >= rel_open, hangi girdiyle olursa olsun (bkz. fonksiyonun
    kendi kanıtı) — OR-Tools'un SetRange'i asla ters bir aralık almaz."""
    cases = [
        (540, 1080, 0), (540, 1080, 720), (540, 1080, 1439),
        (1320, 120, 0), (1320, 120, 1080), (1320, 120, 1439),
        (0, 240, 1080), (0, 1439, 0),
    ]
    for open_m, close_m, day_start in cases:
        rel_open, rel_close = _day_relative_window(open_m, close_m, day_start)
        assert rel_close >= rel_open, (open_m, close_m, day_start)


# ─── _window_overlaps_day ─────────────────────────────────────────────────────

def test_window_overlaps_day_same_day_window_fits():
    assert _window_overlaps_day(540, 1080, 540, 1080) is True


def test_window_overlaps_day_overnight_place_within_overnight_planning_day():
    assert _window_overlaps_day(1320, 120, 1080, 60) is True  # gün de overnight


def test_window_overlaps_day_overnight_place_incompatible_with_daytime_planning_day():
    """Case D: mekan 22:00-02:00, planlama 09:00-18:00 — hiç örtüşmez."""
    assert _window_overlaps_day(1320, 120, 540, 1080) is False


def test_window_overlaps_day_partial_overlap_still_counts():
    """Case C: mekan 00:00-04:00, planlama 18:00→01:00 — pencere KISMEN
    örtüşüyor (00:00-01:00 kısmı planlama içinde) — bu yine de 'örtüşür'
    sayılmalı."""
    assert _window_overlaps_day(0, 240, 1080, 60) is True


# ─── _resolve_arrival ─────────────────────────────────────────────────────────

def test_resolve_arrival_waits_silently_for_opening():
    arrival, conflict = _resolve_arrival(current_time=500, day_start=500, day_end=1080, open_m=540, close_m=1080)
    assert arrival == 540
    assert conflict is False


def test_resolve_arrival_within_window_no_wait_needed():
    arrival, conflict = _resolve_arrival(current_time=600, day_start=540, day_end=1080, open_m=540, close_m=1080)
    assert arrival == 600
    assert conflict is False


def test_resolve_arrival_after_closing_same_day_conflicts():
    """Mevcut davranış (bu milestone ÖNCESİ de aynı) — bkz.
    test_optimization_strategy.py'nin kendi eşdeğer testi."""
    arrival, conflict = _resolve_arrival(current_time=540, day_start=540, day_end=1080, open_m=420, close_m=480)
    assert arrival == 540
    assert conflict is True


def test_resolve_arrival_overnight_window_before_opening_waits():
    arrival, conflict = _resolve_arrival(current_time=1080, day_start=1080, day_end=1500, open_m=1320, close_m=120)
    assert arrival == 1320  # 22:00
    assert conflict is False


def test_resolve_arrival_overnight_window_valid_post_midnight():
    arrival, conflict = _resolve_arrival(current_time=1450, day_start=1080, day_end=1500, open_m=1320, close_m=120)
    assert arrival == 1450  # zaten pencere içinde, beklemeye gerek yok
    assert conflict is False


def test_resolve_arrival_overnight_window_invalid_post_closing():
    arrival, conflict = _resolve_arrival(current_time=1600, day_start=1080, day_end=1500, open_m=1320, close_m=120)
    assert conflict is True


def test_resolve_arrival_case_c_early_place_window_shifts_to_tonight():
    """Case C: planlama 18:00→01:00, mekan 00:00-04:00 — gün başında
    (current_time=day_start) çağrılırsa, ERTESİ takvim gününün 00:00'ına
    kadar bekler (dünün geçmiş penceresine DEĞİL)."""
    arrival, conflict = _resolve_arrival(current_time=1080, day_start=1080, day_end=1500, open_m=0, close_m=240)
    assert arrival == 1440  # 1080 + 360 = ertesi günün 00:00'ı, sürekli eksende
    assert conflict is False


def test_resolve_arrival_case_d_incompatible_window_no_infinite_shift():
    """Case D: planlama 09:00-18:00 (overnight DEĞİL), mekan 22:00-02:00 —
    kaydırma UYGULANMAZ (ertesi tekrar da gün bütçesinin dışında kalır),
    mevcut varış DEĞİŞMEDEN döner (arayan taraf — greedy'nin flush/taşma
    mekanizması — bunu doğal olarak ele alır)."""
    arrival, conflict = _resolve_arrival(current_time=540, day_start=540, day_end=1080, open_m=1320, close_m=120)
    assert arrival == 1320  # açılışa kadar bekler (mevcut davranış, DEĞİŞMEDİ)
    assert conflict is False  # henüz kapanmadı, henüz çakışma yok


def test_resolve_arrival_equal_open_close_always_conflicts():
    """Dejenere (open == close) bir pencere HER ZAMAN çakışır — mevcut
    sözleşme (Req 2 'equal start/end semantics'), overnight desteğinden
    etkilenmedi."""
    arrival, conflict = _resolve_arrival(current_time=720, day_start=540, day_end=1080, open_m=720, close_m=720)
    assert conflict is True
