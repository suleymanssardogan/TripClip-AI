"""
ORToolsRouteOptimizationStrategy birim testleri — DB/HTTP yok, yalnızca
strateji. GreedyDistanceStrategy'nin kendi test dosyasıyla
(test_optimization_strategy.py) aynı fixture deseni ve — mümkün olduğunca —
aynı test senaryoları, böylece iki stratejinin aynı sözleşmeyi (hiçbir durak
kaybolmaz, aynı OptimizationResult şekli, aynı uyarı metinleri) sağladığı
doğrudan görülebilir. Ek olarak: determinism ve büyük durak kümeleri, bu
stratejiye özgü riskler (solver, greedy'nin aksine potansiyel olarak
zamanlama/rastgelelik taşıyabilir — bkz. ortools_strategy.py "Determinism").

Servis/repository katmanı test_trip_optimization.py'de (entegrasyon).
İki stratejinin şema uyumluluğu test_strategy_comparison.py'de.
"""
import time

from app.domain.optimization.models import PlaceInput, OptimizationConstraints
from app.infrastructure.optimization.ortools_strategy import ORToolsRouteOptimizationStrategy


def _place(place_id, name, lat, lng, category=None, opening_hours=None) -> PlaceInput:
    return PlaceInput(place_id=place_id, name=name, lat=lat, lng=lng, category=category, opening_hours=opening_hours)


def _run(places, **overrides):
    constraints = OptimizationConstraints(**overrides)
    return ORToolsRouteOptimizationStrategy().optimize(places, constraints)


def test_strategy_name_is_ortools():
    assert ORToolsRouteOptimizationStrategy().name == "ortools"


# ─── Edge case: 0 places ────────────────────────────────────────────────────

def test_empty_place_list_returns_empty_result():
    result = _run([])
    assert result.days == []
    assert result.total_distance_km == 0.0
    assert result.warnings == []
    assert result.optimization_score == 100.0


# ─── Edge case: 1 place ─────────────────────────────────────────────────────

def test_single_place_is_scheduled_at_day_start():
    result = _run([_place(1, "Ayasofya", 41.0086, 28.9802)])
    assert len(result.days) == 1
    stop = result.days[0].stops[0]
    assert stop.day_index == 0
    assert stop.order_index == 0
    assert stop.arrival_time == "09:00"
    assert stop.travel_time_to_next_minutes is None
    assert stop.travel_distance_to_next_km is None
    assert result.total_distance_km == 0.0


# ─── Edge case: 2 places ────────────────────────────────────────────────────

def test_two_places_both_scheduled():
    # n<=2 solver'ı hiç devreye sokmadan kısa devre yapar (bkz.
    # ortools_strategy._solve_visit_order) — yine de sözleşme aynı: her iki
    # durak da kaybolmadan planlanmalı.
    result = _run([
        _place(1, "A", 41.0, 29.0),
        _place(2, "B", 41.05, 29.05),
    ])
    ids = {stop.place_id for day in result.days for stop in day.stops}
    assert ids == {1, 2}
    assert sum(len(d.stops) for d in result.days) == 2


# ─── Duplicate handling is NOT the strategy's job ───────────────────────────

def test_strategy_does_not_dedupe_by_itself():
    """Dedup, OptimizationService'in sorumluluğu (bkz.
    test_optimization_strategy.py'deki aynı testin greedy karşılığı) —
    strateji kendisine verilen listeyi olduğu gibi işler."""
    p = _place(1, "Aynı Mekan", 41.0, 29.0)
    result = _run([p, p])
    assert sum(len(d.stops) for d in result.days) == 2


# ─── Multiple cities ─────────────────────────────────────────────────────────

def test_multiple_cities_all_places_represented_no_duplicates():
    istanbul = [
        _place(1, "Ayasofya", 41.0086, 28.9802),
        _place(2, "Topkapı Sarayı", 41.0115, 28.9833),
    ]
    cappadocia = [
        _place(3, "Göreme Açık Hava Müzesi", 38.6425, 34.8288),
        _place(4, "Uçhisar Kalesi", 38.6297, 34.8117),
    ]
    result = _run(istanbul + cappadocia)
    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == [1, 2, 3, 4]
    assert len(ids) == len(set(ids))


# ─── Impossible constraints ──────────────────────────────────────────────────

def test_impossible_day_budget_still_returns_all_stops_with_warning():
    """1 saatlik gün bütçesine 6 müze (90dk/tanesi) sığmaz — greedy'nin
    'forced last day overflow' davranışıyla aynı sözleşme: hiçbir durak
    düşürülmez, bunun yerine bir uyarı eklenir (fail gracefully)."""
    places = [_place(i, f"Müze {i}", 41.0 + i * 0.3, 29.0 + i * 0.3, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:00", duration_days=1)
    assert len(result.days) == 1
    assert len(result.days[0].stops) == 6
    assert any("sığmayan duraklar" in w for w in result.warnings)


def test_equal_start_and_end_time_falls_back_to_default_window():
    """`end_time == start_time` normalde OptimizationService'te reddedilir
    (bkz. "Overnight Time Ranges" — eşit değerler HÂLÂ geçersiz, mevcut
    sözleşmenin korunan kısmı), ama strateji tek başına çağrılırsa çökmez,
    sessizce varsayılana düşer — greedy ile birebir aynı savunma."""
    result = _run([_place(1, "A", 41.0, 29.0)], preferred_start_time="12:00", preferred_end_time="12:00")
    assert result.days[0].stops[0].arrival_time == "09:00"


def test_end_time_before_start_time_is_now_a_valid_overnight_window():
    """`18:00 → 09:00` ARTIK geçerli bir overnight planlama penceresi
    (15 saat) — fallback'e DÜŞMEZ, tek mekan doğrudan 18:00'de (day_start)
    planlanır. Bu, önceki milestone'un 'end <= start her zaman fallback'
    davranışının kasıtlı olarak DEĞİŞTİĞİ nokta (bkz. "Overnight Time
    Ranges")."""
    result = _run([_place(1, "A", 41.0, 29.0)], preferred_start_time="18:00", preferred_end_time="09:00")
    assert result.days[0].stops[0].arrival_time == "18:00"


# ─── Unavailable / degenerate coordinates ───────────────────────────────────

def test_identical_coordinates_all_places_still_scheduled():
    """Aynı koordinata sahip birden çok mekan (ör. konum verisi eksik/varsayılan
    olduğunda) — mesafe her çift için 0, solver'ın çökmemesi/atlamaması gerekir."""
    places = [_place(i, f"Mekan {i}", 41.0, 29.0) for i in range(5)]
    result = _run(places)
    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == [0, 1, 2, 3, 4]
    assert result.total_distance_km == 0.0


# ─── Opening hours unavailable ───────────────────────────────────────────────

def test_missing_opening_hours_generates_unavailable_warning_not_conflict():
    result = _run([_place(1, "Bilinmeyen Saat", 41.0, 29.0)])
    assert not any("çakışıyor" in w for w in result.warnings)
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)


def test_arrival_before_opening_is_clipped_silently():
    result = _run([_place(1, "Geç Açılan Mekan", 41.0, 29.0, opening_hours="10:00-18:00")])
    stop = result.days[0].stops[0]
    assert stop.arrival_time == "10:00"
    assert not any("çakışıyor" in w for w in result.warnings)


def test_arrival_after_closing_gets_conflict_warning():
    result = _run([_place(1, "Erken Kapanan Mekan", 41.0, 29.0, opening_hours="07:00-08:00")])
    assert any("çakışıyor" in w for w in result.warnings)


# ─── Multiple days ────────────────────────────────────────────────────────────

def test_places_split_across_days_when_day_budget_exceeded():
    places = [_place(i, f"Müze {i}", 41.0 + i * 0.2, 29.0 + i * 0.2, category="museum") for i in range(8)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="12:00")
    assert len(result.days) > 1
    assert sum(len(d.stops) for d in result.days) == 8


def test_duration_days_not_provided_derives_day_count():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(6)]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00", duration_days=None)
    assert len(result.days) >= 2


def test_start_date_produces_calendar_dates_per_day():
    places = [_place(i, f"Mekan {i}", 41.0 + i * 0.5, 29.0 + i * 0.5, category="museum") for i in range(4)]
    result = _run(
        places, preferred_start_time="09:00", preferred_end_time="11:00",
        duration_days=None, start_date="2026-09-01",
    )
    assert result.days[0].date == "2026-09-01"
    if len(result.days) > 1:
        assert result.days[1].date == "2026-09-02"


# ─── Large place sets ─────────────────────────────────────────────────────────

def test_large_place_set_completes_quickly_and_includes_every_place():
    places = [
        _place(i, f"Mekan {i}", 36.0 + (i % 17) * 0.3, 27.0 + ((i * 7) % 23) * 0.3)
        for i in range(60)
    ]
    start = time.monotonic()
    result = _run(places, duration_days=None)
    elapsed = time.monotonic() - start

    ids = [stop.place_id for day in result.days for stop in day.stops]
    assert sorted(ids) == list(range(60))
    assert len(ids) == len(set(ids))
    # solution_limit-bound arama — gerçekçi gezi boyutlarında (onlarca durak)
    # saniyeler sürer, time_limit güvenlik ağına (5s) hiç yaklaşmaz.
    assert elapsed < 10.0


# ─── Score bounds ─────────────────────────────────────────────────────────────

def test_score_never_negative_even_with_many_warnings():
    places = [
        _place(1, "A", 41.0, 29.0),
        _place(2, "B", 38.6, 34.8),   # ~700km
        _place(3, "C", 36.9, 30.7),   # Antalya
        _place(4, "D", 39.9, 32.8),   # Ankara
    ]
    result = _run(places)
    assert 0.0 <= result.optimization_score <= 100.0


# ─── Determinism (bkz. ortools_strategy.py "Determinism") ───────────────────

def _stop_signature(result):
    return [
        (s.place_id, s.day_index, s.order_index, s.arrival_time, s.departure_time,
         s.travel_time_to_next_minutes, s.travel_distance_to_next_km)
        for day in result.days for s in day.stops
    ]


def test_same_input_produces_identical_result_across_repeated_runs():
    places = [
        _place(i, f"Mekan {i}", 41.0 + (i * 0.37) % 3, 29.0 + (i * 0.53) % 3,
               category=("museum" if i % 2 else None))
        for i in range(15)
    ]
    constraints = dict(
        preferred_start_time="09:00", preferred_end_time="18:00",
        duration_days=None, start_date="2026-09-01",
    )

    results = [_run(places, **constraints) for _ in range(5)]
    first_signature = _stop_signature(results[0])

    for other in results[1:]:
        assert _stop_signature(other) == first_signature
        assert other.total_distance_km == results[0].total_distance_km
        assert other.total_travel_time_minutes == results[0].total_travel_time_minutes
        assert other.optimization_score == results[0].optimization_score
        assert other.warnings == results[0].warnings


def test_determinism_holds_across_fresh_strategy_instances():
    """Strateji durumsuz (stateless) olmalı — yeni bir instance kullanmak
    sonucu değiştirmemeli. Registry'de tek bir paylaşılan instance var, ama
    bu varsayımı hiç kanıtlamadan bırakmayalım."""
    places = [_place(i, f"Mekan {i}", 40.0 + i * 0.4, 28.0 + i * 0.4) for i in range(10)]
    constraints = OptimizationConstraints()

    r1 = ORToolsRouteOptimizationStrategy().optimize(places, constraints)
    r2 = ORToolsRouteOptimizationStrategy().optimize(places, constraints)

    assert _stop_signature(r1) == _stop_signature(r2)


# ═══════════════════════════════════════════════════════════════════════════
# Hard opening-hours time windows (bkz. ortools_strategy.py "Hard opening-
# hours time windows") — GreedyDistanceStrategy'nin aksine, burada açılış
# saatleri artık rota SIRALAMASINI etkileyen sert bir kısıt, yalnızca
# son-işleme sırasında kırpılan/uyarılan yumuşak bir sinyal değil.
# ═══════════════════════════════════════════════════════════════════════════

# ─── Place open all day ──────────────────────────────────────────────────────

def test_place_open_all_day_is_never_constrained_or_warned():
    result = _run([
        _place(1, "Her Zaman Açık", 41.00, 29.00, opening_hours="00:00-23:59"),
        _place(2, "Normal", 41.05, 29.05),
    ])
    assert not any("çakışıyor" in w for w in result.warnings)
    assert not any("gevşetildi" in w for w in result.warnings)
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]


# ─── Narrow opening window forces reordering vs. pure distance ──────────────

def test_narrow_window_forces_reordering_relative_to_pure_distance():
    """Dört mekan — A(batı), C(orta, YALNIZCA 09:00-09:30 açık), B(doğu),
    D(güney). Saf mesafe-minimizasyonu C'yi rotanın ortasında bir yere
    koyar; sert pencere C'yi İLK durağa zorlar — bu, salt son-işlemede
    'kırpma/uyar' ile ELDE EDİLEMEZ bir sıralama kararı, tam da bu
    milestone'un kanıtlamak istediği şey."""
    places = [
        _place(1, "A-batı", 41.00, 27.50),
        _place(2, "C-orta", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(3, "B-doğu", 41.00, 30.50),
        _place(4, "D-güney", 39.50, 29.00),
    ]
    result = _run(places)

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2, 3, 4]  # hiçbir durak kaybolmadı
    assert not any("gevşetildi" in w for w in result.warnings)  # sağlanabilir, gevşetme yok

    first_stop = result.days[0].stops[0]
    assert first_stop.place_id == 2  # C-orta zorunlu olarak ilk durak
    assert first_stop.arrival_time == "09:00"

    # Sert kısıtı sağlamanın bir mesafe bedeli var — bu, salt mesafeyle
    # asla seçilmeyecek bir sıralama (bkz. docs "Examples").
    unconstrained_places = [_place(p.place_id, p.name, p.lat, p.lng) for p in places]
    unconstrained = _run(unconstrained_places)
    assert result.total_distance_km > unconstrained.total_distance_km


# ─── Multiple places with compatible windows ────────────────────────────────

def test_multiple_places_with_compatible_windows_all_satisfied_no_conflicts():
    result = _run([
        _place(1, "P1", 41.00, 29.00, opening_hours="09:00-10:00"),
        _place(2, "P2", 41.05, 29.05, opening_hours="10:15-11:15"),
        _place(3, "P3", 41.10, 29.10, opening_hours="11:30-12:30"),
    ])
    assert not any("çakışıyor" in w for w in result.warnings)
    assert not any("gevşetildi" in w for w in result.warnings)

    stops_by_id = {s.place_id: s for d in result.days for s in d.stops}
    assert stops_by_id[1].arrival_time == "09:00"
    # Her durağın varışı KENDİ penceresi içinde olmalı.
    windows = {1: ("09:00", "10:00"), 2: ("10:15", "11:15"), 3: ("11:30", "12:30")}
    for place_id, (open_t, close_t) in windows.items():
        arrival = stops_by_id[place_id].arrival_time
        assert open_t <= arrival <= close_t, f"place {place_id}: {arrival} not in [{open_t},{close_t}]"


# ─── Incompatible-within-a-single-day windows → day-aware resolves them ────
#
# NOT: Bu test, day-aware milestone'dan ÖNCE "impossible route, gevşetildi"
# bekliyordu (tek-sürekli-zaman-çizelgesi modeliyle küresel olarak
# imkansızdı). Artık bu senaryonun GÜN-FARKINDA doğru cevabı var (biri 1.
# güne, diğeri 2. güne) — bkz. modül docstring "The single-continuous-
# timeline bug" ve aşağıdaki
# `test_two_incompatible_same_window_places_satisfied_across_separate_days`
# (spesifikasyonun 8. "critical regression test" gereksinimi).

def test_two_far_apart_same_window_places_no_longer_falsely_relaxed():
    """Bir önceki (day-aware olmayan) modelde bu senaryo 'imkansız' sayılıp
    HER İKİ sert kısıt da atılıyordu. Day-aware modelde artık HİÇ gevşetme
    olmadan, ikisi de kendi gününde tam zamanında karşılanıyor."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ])
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]  # hiçbir durak silinmedi/atlanmadı
    assert not any("gevşetildi" in w for w in result.warnings)
    assert not any("çakışıyor" in w for w in result.warnings)
    assert len(result.days) == 2

    stops_by_id = {s.place_id: s for d in result.days for s in d.stops}
    assert stops_by_id[1].arrival_time == "09:00"
    assert stops_by_id[2].arrival_time == "09:00"


def test_incompatible_windows_result_still_has_valid_schema_when_genuinely_infeasible():
    """`duration_days=1` iki mekanı TEK bir güne zorlar — bu durumda
    senaryo GERÇEKTEN imkansız (bkz.
    `test_impossible_multi_day_schedule_still_relaxes_gracefully` aşağıda).
    Dönen OptimizationResult yine de normal sonuçla BİREBİR aynı şemayı
    korur — çağıran taraf özel bir 'hata' dalı işlemek zorunda değil."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ], duration_days=1)
    assert isinstance(result.days, list)
    assert isinstance(result.warnings, list)
    assert isinstance(result.total_distance_km, float)
    assert isinstance(result.optimization_score, float)
    assert 0.0 <= result.optimization_score <= 100.0
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]


# ─── Missing opening-hours metadata alongside constrained places ───────────

def test_places_without_hours_remain_optimizable_alongside_constrained_ones():
    """Spesifikasyonun 3. gereksinimi: açılış saati verisi olmayan mekanlar
    hâlâ serbestçe optimize edilebilmeli — sert pencereli mekanların
    ETRAFINA konumlandırılabilirler, kısıtlanmazlar."""
    places = [
        _place(1, "Sabit Pencere", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Bilinmiyor A", 41.02, 29.02),
        _place(3, "Bilinmiyor B", 41.20, 29.20),
        _place(4, "Bilinmiyor C", 41.40, 29.40),
    ]
    result = _run(places)
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2, 3, 4]
    assert not any("gevşetildi" in w for w in result.warnings)
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)


# ─── Multiple days combined with a hard window ──────────────────────────────

def test_hard_window_combined_with_multi_day_splitting_still_works():
    """Spesifikasyonun 5. gereksinimi: çok-günlü davranış korunmalı. Sıkı bir
    günlük bütçe + bir sert pencere birlikte hiçbir durağı kaybettirmemeli,
    birden fazla gün üretmeye devam etmeli."""
    places = [
        _place(i, f"Müze {i}", 41.0 + i * 0.2, 29.0 + i * 0.2, category="museum")
        for i in range(8)
    ]
    places[3] = _place(3, "Müze 3", 41.0 + 3 * 0.2, 29.0 + 3 * 0.2, category="museum", opening_hours="09:00-10:30")

    result = _run(places, preferred_start_time="09:00", preferred_end_time="12:00")

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == list(range(8))
    assert len(result.days) > 1


# ─── Overnight time ranges — hard-constrained, not skipped ──────────────────
#
# Önceki milestone'da bu bölüm "overnight pencereler desteklenmiyor, sert
# kısıt atlanıyor" başlığı altındaydı — bkz. ortools_strategy.py "Overnight
# time ranges — hard-constrained, not skipped" ve
# greedy_distance_strategy.py "Overnight Time Ranges" için YENİ modelin
# tam açıklaması. Bu bölüm o eski davranışın YERİNE geçiyor.

def test_overnight_place_window_is_hard_constrained_not_skipped():
    """Tek mekan, overnight açılış penceresi (22:00-02:00), overnight
    PLANLAMA penceresi (18:00→01:00) — mekan artık SERT kısıtlı olarak
    (unconstrained_ids'e DÜŞMEDEN) planlanır: açılıştan önce sessizce
    bekler, hiçbir çakışma uyarısı üretmez, ÇÖKMEZ (bkz. tarihsel not:
    ham (open>close) bir çift SetRange'e verilirse solver çöker — bu artık
    asla olamaz)."""
    result = _run(
        [_place(1, "Gece Kulübü", 41.00, 29.00, opening_hours="22:00-02:00")],
        preferred_start_time="18:00", preferred_end_time="01:00",
    )
    stop = result.days[0].stops[0]
    assert stop.arrival_time == "22:00"
    assert not any("çakışıyor" in w for w in result.warnings)


def test_overnight_planning_window_accepts_valid_post_midnight_place_window():
    """docs/trip-optimizer.md 'Overnight Time Ranges → Case C': planlama
    18:00→01:00, mekan 00:00-04:00 — 00:00 mekanın kendi açılışı, planlama
    penceresinin 01:00 kesintisinden ÖNCE, bu yüzden GEÇERLİ bir varış."""
    result = _run(
        [_place(1, "Gece Yarısı Sonrası", 41.00, 29.00, opening_hours="00:00-04:00")],
        preferred_start_time="18:00", preferred_end_time="01:00",
    )
    stop = result.days[0].stops[0]
    assert stop.arrival_time == "00:00"
    assert not any("çakışıyor" in w for w in result.warnings)


def test_overnight_planning_window_place_already_closed_gets_conflict_warning():
    """Planlama 18:00→01:00 (overnight) olsa bile, bir mekanın penceresi bu
    planlama gününü hiç örtmüyorsa (burada: yalnızca 16:00-17:00, günün
    18:00 başlangıcından ÖNCE kapanmış, ertesi tekrarı da 01:00 kesintisinin
    ÖTESİNDE) hâlâ 'çakışıyor' uyarısı almalı — sert kısıt unconstrained'e
    düşer (bkz. `_window_overlaps_day`), ama yumuşak son-işleme kontrolü
    (`_resolve_arrival`, her iki stratejide de KOŞULSUZ çalışır) yine de
    gerçek varışı değerlendirir."""
    result = _run(
        [_place(1, "Öğleden Sonra Mekanı", 41.00, 29.00, opening_hours="16:00-17:00")],
        preferred_start_time="18:00", preferred_end_time="01:00",
    )
    assert any("çakışıyor" in w for w in result.warnings)


def test_overnight_place_window_incompatible_with_non_overnight_day_is_unconstrained_not_lost():
    """docs/trip-optimizer.md 'Overnight Time Ranges → Case D': planlama
    09:00-18:00 (overnight DEĞİL), mekan 22:00-02:00 — bu pencere BU günü
    hiç örtmüyor (`_window_overlaps_day` False), bu yüzden sert kısıt hiç
    uygulanmaz (mevcut 'açılış saati bilinmeyen mekan' ile aynı muamele) —
    ama mekan yine de PLANLANIR, kaybolmaz, çökme olmaz; sahte bir 'ikinci
    gün' de İCAT EDİLMEZ (gün sayısı bu tek mekan/normal mekan çifti için
    değişmeden kalır)."""
    result = _run(
        [
            _place(1, "Gece Kulübü", 41.00, 29.00, opening_hours="22:00-02:00"),
            _place(2, "Normal", 41.05, 29.05),
        ],
        preferred_start_time="09:00", preferred_end_time="18:00",
    )
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]


def test_overnight_window_mixed_with_a_same_day_hard_window_does_not_crash():
    """Ters (overnight) bir pencere İLE aynı-gün geçerli bir sert pencerenin
    AYNI çağrıda bir arada bulunması — solver'a ASLA geçersiz (lower>upper)
    bir CumulVar aralığı sızmamalı (bkz. `_day_relative_window`'un kendi
    `rel_close >= rel_open` garantisi), üç mekan da kaybolmamalı."""
    result = _run(
        [
            _place(1, "Gece Kulübü", 41.00, 29.00, opening_hours="22:00-02:00"),
            _place(2, "Sabit Pencere", 41.05, 29.05, opening_hours="19:00-20:00"),
            _place(3, "Normal", 41.10, 29.10),
        ],
        preferred_start_time="18:00", preferred_end_time="01:00",
    )
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2, 3]


# ─── Determinism with hard windows active ────────────────────────────────────

def test_determinism_holds_with_hard_windows_active():
    places = [
        _place(1, "A-batı", 41.00, 27.50),
        _place(2, "C-orta", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(3, "B-doğu", 41.00, 30.50),
        _place(4, "D-güney", 39.50, 29.00),
    ]
    results = [_run(places) for _ in range(5)]
    first = _stop_signature(results[0])
    for other in results[1:]:
        assert _stop_signature(other) == first
        assert other.warnings == results[0].warnings
        assert other.total_distance_km == results[0].total_distance_km


def test_determinism_holds_for_impossible_route_fallback():
    """İmkansız durumda bile (fallback yolu) sonuç deterministik olmalı —
    her çağrı aynı mesafe-yalnızca sıraya VE aynı 'gevşetildi' uyarısına
    düşmeli."""
    places = [
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ]
    results = [_run(places) for _ in range(5)]
    first = _stop_signature(results[0])
    for other in results[1:]:
        assert _stop_signature(other) == first
        assert other.warnings == results[0].warnings


# ─── Performance protection: windows must not cause unbounded solving ──────

def test_large_place_set_with_scattered_hard_windows_completes_quickly():
    """Spesifikasyonun 8. gereksinimi: açılış saati kısıtları sınırsız
    aramaya yol açmamalı — aynı solution_limit/time_limit güvenlik ağı
    (bkz. ortools_strategy.py 'Performance protection')."""
    places = [
        _place(i, f"Mekan {i}", 36.0 + (i % 17) * 0.3, 27.0 + ((i * 7) % 23) * 0.3)
        for i in range(40)
    ]
    # Her 5 mekandan birine geniş (pratikte serbest) bir pencere ver —
    # dimension'ı gerçekten devreye sokar ama gerçek bir kısıt getirmez.
    for i in range(0, 40, 5):
        places[i] = _place(
            i, f"Mekan {i}", places[i].lat, places[i].lng, opening_hours="00:00-23:59"
        )

    start = time.monotonic()
    result = _run(places, duration_days=None)
    elapsed = time.monotonic() - start

    ids = [s.place_id for d in result.days for s in d.stops]
    assert sorted(ids) == list(range(40))
    assert len(ids) == len(set(ids))
    # Tek bir sert-kısıtlı solve + (yalnızca gerekirse) tek bir fallback
    # solve — ikisi de aynı 5s time_limit'e tabi, bu yüzden üst sınır ~10s.
    assert elapsed < 15.0


def test_incompatible_windows_infeasibility_detected_quickly_not_at_time_limit():
    """İmkansız bir durumun HEMEN (solution_limit'e/time_limit'e dayanmadan)
    tespit edildiğini doğrular — depo kenarları hep 0 maliyetli olduğundan
    saf mesafe kısmı her zaman uygun, yalnızca zaman boyutu infeasible;
    OR-Tools bunu CP-propagation ile hızlıca fark eder."""
    places = [
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ]
    start = time.monotonic()
    _run(places)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0  # tek time_limit'in altında, iki solve'un TOPLAMI dahil


# ─── Preserved semantics: score formula, API contract ──────────────────────

def test_score_semantics_preserved_more_warnings_still_reduce_score_by_five():
    """Skor formülü DEĞİŞMEDİ (bkz. spesifikasyonun 5. gereksinimi) — yeni
    'gevşetildi' uyarısı da tıpkı diğer uyarılar gibi yalnızca
    warning_penalty'ye (uyarı başına -5, en fazla -30) katkıda bulunur,
    ayrı bir puanlama mekanizması eklenmedi."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ])
    warning_penalty = min(30.0, len(result.warnings) * 5)
    avg_km = result.total_distance_km  # tek segment (n=2), stops-1=1
    travel_penalty = min(40.0, avg_km * 2)
    expected_score = round(max(0.0, 100.0 - travel_penalty - warning_penalty), 1)
    assert result.optimization_score == expected_score


# ═══════════════════════════════════════════════════════════════════════════
# Day-aware scheduling (bkz. ortools_strategy.py "Day-aware scheduling") —
# açılış saati kısıtları artık HANGİ GÜNE denk geldiklerine göre, o günün
# KENDİ yerel saatine karşı değerlendiriliyor; tek-sürekli-zaman-çizelgesi
# kusurunun (bkz. modül docstring "The single-continuous-timeline bug")
# kapatıldığını doğrudan kanıtlayan testler.
# ═══════════════════════════════════════════════════════════════════════════

# ─── Critical regression test (spesifikasyonun 8. gereksinimi) ─────────────

def test_two_incompatible_same_window_places_satisfied_across_separate_days():
    """BU, spesifikasyonun 8. 'critical regression test' gereksinimidir:
    eski (tek-sürekli-zaman-çizelgesi) modelde bu tam senaryo — iki mekan,
    ikisi de yalnızca 09:00-09:30 açık, aralarında saatlerce sürecek bir
    mesafe — KÜRESEL OLARAK İMKANSIZ sayılıyor ve HER İKİ sert kısıt da
    tamamen atılıyordu (ampirik olarak doğrulandı — bkz. bu milestone'un
    tasarım notları). Day-aware modelde artık doğru cevap bulunuyor: biri
    1. güne, diğeri 2. güne — ikisi de KENDİ gününün açılış saatinde,
    HİÇBİR gevşetme olmadan karşılanıyor. Bu test, eski davranışa asla geri
    dönülmediğini garanti eder."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ])

    assert not any("gevşetildi" in w for w in result.warnings)
    assert not any("çakışıyor" in w for w in result.warnings)
    assert len(result.days) == 2

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]

    stops_by_id = {s.place_id: s for d in result.days for s in d.stops}
    for place_id in (1, 2):
        arrival = stops_by_id[place_id].arrival_time
        assert "09:00" <= arrival <= "09:30", f"place {place_id}: {arrival} dışında pencere"

    # İki mekan da FARKLI günlere düşmeli — ikisi AYNI güne konsaydı
    # (09:00-09:30 penceresi ikisi için de aynı anda geçerli olamayacağından)
    # bu genuinely infeasible olurdu.
    day_of = {s.place_id: d.day_index for d in result.days for s in d.stops}
    assert day_of[1] != day_of[2]


# ─── Constrained stop on Day 1 / Day 2 ───────────────────────────────────────

def test_constrained_stop_scheduled_on_day_one():
    """Sert pencereli mekan, hemen yanındaki bir mekanla birlikte 1. güne
    (day_index=0) rahatça sığar; üçüncü (uzak) mekan kendi günü gerektirir.
    1. günün mekanı, o günün KENDİ yerel saatine karşı doğru karşılanmalı."""
    places = [
        _place(1, "Sabit", 41.00, 29.00, opening_hours="09:00-09:45"),
        _place(2, "Yakın", 41.02, 29.02),   # Sabit'e çok yakın -- aynı güne sığar
        _place(3, "Uzak", 41.80, 29.80),    # uzak -- kendi günü gerekir
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00")

    day0_ids = {s.place_id for s in result.days[0].stops}
    assert 1 in day0_ids, f"Sabit (place_id=1) 1. güne düşmedi: {day0_ids}"

    stop1 = next(s for d in result.days for s in d.stops if s.place_id == 1)
    assert stop1.day_index == 0
    assert "09:00" <= stop1.arrival_time <= "09:45"
    assert not any("çakışıyor" in w for w in result.warnings)
    assert not any("gevşetildi" in w for w in result.warnings)


def test_constrained_stop_scheduled_on_day_two():
    """Aynı senaryo, ama sert pencereli mekan diğer iki mekandan SONRA
    planlanacak biçimde — 2. güne (day_index=1) düşmeli ve 2. GÜNÜN KENDİ
    (dünden bağımsız, taze) yerel saatine karşı doğru karşılanmalı. Bu,
    spesifikasyonun 1. gereksinimini ('Day 2 stop must be checked against
    Day 2's timeline, not the previous day's cumulative minutes') doğrudan
    sınar."""
    places = [
        _place(1, "Diger1", 41.00, 29.00),
        _place(2, "Diger2", 41.30, 29.30),
        _place(3, "Sabit", 41.60, 29.60, opening_hours="09:00-09:45"),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00")

    assert len(result.days) >= 2  # üç mekan, sıkı bütçe -> birden fazla gün gerekiyor
    stop3 = next(s for d in result.days for s in d.stops if s.place_id == 3)
    # Hangi güne düşerse düşsün (solver kararı), o günün KENDİ yerel saatine
    # göre pencere karşılanmalı — day 1'in "dünden miras" bir zamanına göre değil.
    assert "09:00" <= stop3.arrival_time <= "09:45"
    assert not any("çakışıyor" in w for w in result.warnings)
    assert not any("gevşetildi" in w for w in result.warnings)


# ─── Same opening hours on multiple days / compatible multi-day windows ────

def test_same_opening_hours_on_multiple_days_each_satisfied_locally():
    """Dört mekan, HEPSİ aynı '09:00-09:45' penceresini paylaşıyor — her
    biri KENDİ gününde bu pencereyi karşılamalı (aynı HH:MM değeri, her gün
    yeniden kullanılabilir — bkz. docs 'Assumptions: opening hours are
    daily-only'). Hiçbiri gevşetilmemeli."""
    places = [
        _place(i, f"M{i}", 41.0 + i * 0.3, 29.0 + i * 0.3, opening_hours="09:00-09:45")
        for i in range(4)
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:30")

    assert len(result.days) == 4  # her mekan aynı dar pencereyi istiyor -> birer gün
    assert not any("gevşetildi" in w for w in result.warnings)
    assert not any("çakışıyor" in w for w in result.warnings)
    for day in result.days:
        assert len(day.stops) == 1
        assert "09:00" <= day.stops[0].arrival_time <= "09:45"


def test_compatible_multi_day_windows_different_times_each_day():
    """Farklı (ama her biri kendi gününde tek başına rahatça karşılanabilir)
    pencerelere sahip birkaç mekan — sıkı gün bütçesi çok-günlü dağılıma
    zorluyor, hepsi gevşetmeden karşılanmalı."""
    places = [
        _place(1, "Sabah", 41.00, 29.00, opening_hours="09:00-10:00"),
        _place(2, "Öğlen", 41.30, 29.30, opening_hours="09:30-10:30"),
        _place(3, "İkindi", 41.60, 29.60, opening_hours="09:15-10:15"),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00")

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2, 3]
    assert not any("gevşetildi" in w for w in result.warnings)
    assert not any("çakışıyor" in w for w in result.warnings)


# ─── Travel across a day boundary ────────────────────────────────────────────

def test_travel_to_next_still_computed_across_day_boundary():
    """Bir günün SON durağının 'sıradaki durağa seyahat' bilgisi, mevcut
    davranışla aynı şekilde, gün sınırını AŞARAK (bir sonraki günün İLK
    durağına) hesaplanmaya devam etmeli — bkz. modül docstring
    '_walk_day_groups'. total_distance_km/total_travel_time_minutes de bu
    gün-arası bacağı içermeli."""
    places = [
        _place(1, "Sabit", 41.00, 29.00, opening_hours="09:00-09:45"),
        _place(2, "Diger1", 41.30, 29.30),
        _place(3, "Diger2", 41.60, 29.60),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="11:00")
    assert len(result.days) >= 2

    # Son gün HARİÇ her günün son durağı, sıradaki (başka gündeki) durağa
    # dair seyahat bilgisini taşımalı (None OLMAMALI).
    for day in result.days[:-1]:
        last_stop = day.stops[-1]
        assert last_stop.travel_time_to_next_minutes is not None
        assert last_stop.travel_distance_to_next_km is not None
    # Yalnızca EN SON günün EN SON durağı None olmalı (sıradaki durak yok).
    assert result.days[-1].stops[-1].travel_time_to_next_minutes is None
    assert result.total_distance_km > 0.0


# ─── Service duration crossing a day boundary ───────────────────────────────

def test_service_duration_alone_exceeding_budget_still_scheduled_not_dropped():
    """Tek başına gün bütçesini aşan bir ziyaret süresi (90dk müze, 60dk
    bütçe) — mevcut 'tek durak günü aşabilir' kuralının bu modeldeki
    karşılığı: mekan KAYBOLMAMALI, bir güne (gerekirse zorunlu son güne)
    planlanmalı, asla sessizce düşürülmemeli."""
    places = [
        _place(1, "Uzun Ziyaret", 41.00, 29.00, category="museum"),  # 90dk
        _place(2, "Sabit", 41.30, 29.30, opening_hours="09:00-09:30"),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:00", duration_days=2)

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]  # hiçbir mekan kaybolmadı
    stop1 = next(s for d in result.days for s in d.stops if s.place_id == 1)
    assert stop1.visit_duration_minutes == 90


def test_non_final_day_never_lets_a_stop_silently_spill_past_day_end():
    """Spesifikasyonun 5. gereksinimi: 'A stop must not silently spill into
    another day.' Zorunlu OLMAYAN bir günde, bir durağın dahil edilmesi
    o günün bütçesini (birden fazla durak nedeniyle) aşacaksa, solver o
    durağı YARINA erteler — bugüne sessizce sığdırmaz."""
    # 3 mekan, her biri 60dk ziyaret + aralarında belirgin seyahat -- 60dk'lık
    # bir günlük bütçeye asla ikisi birden sığmaz.
    places = [
        _place(1, "A", 41.00, 29.00),
        _place(2, "B", 41.30, 29.30),
        _place(3, "C", 41.60, 29.60),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:00")
    for day in result.days:
        assert len(day.stops) == 1, "60dk'lık günlük bütçeye birden fazla 60dk'lık ziyaret sığmamalı"


# ─── Impossible multi-day schedule ───────────────────────────────────────────

def test_impossible_multi_day_schedule_still_relaxes_gracefully():
    """`duration_days=1`, iki uzak-ve-aynı-dar-pencereli mekanı TEK bir güne
    zorluyor — bu durumda day-aware model bile gerçekten imkansız (gün
    sayısı kısıtlı, ayrı günlere bölünemiyor). Mevcut gevşetme/fallback
    davranışı devreye girmeli: hiçbir mekan kaybolmaz, açık bir uyarı eklenir."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ], duration_days=1)

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]
    assert len(result.days) == 1
    assert any("gevşetildi" in w for w in result.warnings)


# ─── Missing opening hours (day-aware path) ─────────────────────────────────

def test_missing_opening_hours_in_multi_day_trip_stays_freely_optimizable():
    """Karma bir çok-günlü gezi: bazı mekanların sert penceresi var, bazılarının
    hiç açılış-saati verisi yok — kısıtsız olanlar HERHANGİ bir güne serbestçe
    yerleştirilebilmeli (spesifikasyonun 3. gereksinimi), day-aware döngüde de."""
    places = [
        _place(1, "Sabit", 41.00, 29.00, opening_hours="09:00-09:45"),
        _place(2, "Bilinmiyor A", 41.30, 29.30),
        _place(3, "Bilinmiyor B", 41.60, 29.60),
        _place(4, "Bilinmiyor C", 41.90, 29.90),
    ]
    result = _run(places, preferred_start_time="09:00", preferred_end_time="10:30")
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2, 3, 4]
    assert any("Açılış saatleri bilinmiyor" in w for w in result.warnings)
    assert not any("gevşetildi" in w for w in result.warnings)


# ─── Deterministic repeated execution (day-aware path) ──────────────────────

def test_day_aware_schedule_is_deterministic_across_repeated_runs():
    """Gün-farkında çok-günlü döngü de deterministik olmalı — her günün
    solve çağrısı deterministik VE günler her zaman aynı sırada
    çözüldüğünden, tüm çok-günlü sonuç da deterministiktir."""
    places = [
        _place(1, "Sabit1", 41.00, 29.00, opening_hours="09:00-09:45"),
        _place(2, "Sabit2", 41.30, 29.30, opening_hours="09:15-10:00"),
        _place(3, "Diger1", 41.60, 29.60),
        _place(4, "Diger2", 41.90, 29.90),
        _place(5, "Diger3", 42.20, 30.20),
    ]
    results = [_run(places, preferred_start_time="09:00", preferred_end_time="11:00") for _ in range(5)]

    first = _stop_signature(results[0])
    for other in results[1:]:
        assert _stop_signature(other) == first
        assert other.warnings == results[0].warnings
        assert other.total_distance_km == results[0].total_distance_km
        assert len(other.days) == len(results[0].days)


def test_day_aware_critical_regression_scenario_is_deterministic():
    """Kritik regresyon senaryosunun (bkz. yukarısı) kendisi de deterministik
    olmalı — 5 ardışık çağrı hep aynı gün atamasını/sırasını üretmeli."""
    places = [
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ]
    results = [_run(places) for _ in range(5)]
    first = _stop_signature(results[0])
    for other in results[1:]:
        assert _stop_signature(other) == first
        assert other.warnings == results[0].warnings
