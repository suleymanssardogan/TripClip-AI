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


def test_invalid_time_window_falls_back_to_default_window():
    """end_time <= start_time normalde OptimizationService'te reddedilir,
    ama strateji tek başına çağrılırsa çökmez, sessizce varsayılana düşer —
    greedy ile birebir aynı savunma."""
    result = _run([_place(1, "A", 41.0, 29.0)], preferred_start_time="18:00", preferred_end_time="09:00")
    assert result.days[0].stops[0].arrival_time == "09:00"


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


# ─── Incompatible windows → impossible route, graceful fallback ────────────

def test_incompatible_windows_falls_back_to_distance_only_with_warning():
    """İki mekan, ikisi de yalnızca 09:00-09:30 açık ama ~700km arayla —
    aynı anda ikisini de bu dar pencerede ziyaret etmek FİZİKSEL OLARAK
    imkansız. Sonuç asla eksik/geçersiz olmamalı (spesifikasyonun 4.
    gereksinimi) — her iki mekan da hâlâ tam bir itinerary'de yer almalı,
    yalnızca sert kısıt gevşetildiğini açıkça belirten bir uyarı eklenir."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ])
    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]  # hiçbir durak silinmedi/atlanmadı
    assert any("gevşetildi" in w for w in result.warnings)
    # Gevşetme sonrası, mevcut yumuşak çakışma kontrolü yine en az birini işaretler.
    assert any("çakışıyor" in w for w in result.warnings)


def test_incompatible_windows_result_still_has_valid_schema():
    """İmkansız durumda bile dönen OptimizationResult, normal sonuçla
    BİREBİR aynı şemayı korur — çağıran taraf özel bir 'hata' dalı
    işlemek zorunda değil (spesifikasyonun 'existing OptimizationResult
    contract' gereksinimi)."""
    result = _run([
        _place(1, "Yakın", 41.00, 29.00, opening_hours="09:00-09:30"),
        _place(2, "Uzak", 38.60, 34.80, opening_hours="09:00-09:30"),
    ])
    assert isinstance(result.days, list)
    assert isinstance(result.warnings, list)
    assert isinstance(result.total_distance_km, float)
    assert isinstance(result.optimization_score, float)
    assert 0.0 <= result.optimization_score <= 100.0


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


# ─── Overnight / edge-time window: unsupported by the current model,
# must degrade gracefully (no crash), not silently drop the place ──────────

def test_overnight_window_does_not_crash_and_falls_back_to_soft_warning():
    """'22:00-02:00' gibi gece-yarısını aşan pencereler bu modelde
    desteklenmiyor (bkz. ortools_strategy.py 'Overnight/edge-time
    limitation' — _parse_opening_hours, GreedyDistanceStrategy'den import
    edilir ve DEĞİŞTİRİLMEZ, ters aralığı doğru ayrıştırmaz). Bu strateji bu
    durumda ÇÖKMEMELİ — o tek mekan için sert kısıt atlanır, mevcut yumuşak
    çakışma uyarısı (değişmedi) yine çalışır."""
    places = [
        _place(1, "Gece Kulübü", 41.00, 29.00, opening_hours="22:00-02:00"),
        _place(2, "Normal", 41.05, 29.05),
    ]
    result = _run(places)  # çökmemeli

    ids = sorted(s.place_id for d in result.days for s in d.stops)
    assert ids == [1, 2]
    assert any("çakışıyor" in w for w in result.warnings)


def test_overnight_window_mixed_with_a_real_hard_window_does_not_crash():
    """Ters (overnight) bir pencere İLE geçerli bir sert pencerenin AYNI
    çağrıda bir arada bulunması — solver'a geçersiz bir CumulVar aralığı
    sızmamalı (bkz. `_valid_hard_window`)."""
    result = _run([
        _place(1, "Gece Kulübü", 41.00, 29.00, opening_hours="22:00-02:00"),
        _place(2, "Sabit Pencere", 41.05, 29.05, opening_hours="09:00-10:00"),
        _place(3, "Normal", 41.10, 29.10),
    ])
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
