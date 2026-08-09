"""
Infrastructure katmanı — RouteOptimizationStrategy'nin ikinci implementasyonu:
Google OR-Tools'un kısıt-programlama tabanlı rota çözücüsü.

Bu bir AI/LLM stratejisi DEĞİLDİR — deterministik, klasik bir operations-
research çözücüsüdür (bkz. docs/trip-optimizer.md "Available strategies").

Mimari, GreedyDistanceStrategy'nin kendi "route-first, cluster-second"
ayrımını (bkz. greedy_distance_strategy.py docstring'i) aynen izler, ama
route-first aşamasını değiştirir: nearest-neighbor inşası yerine, OR-Tools'un
RoutingModel'i daha kısa bir açık-yol sıralaması arar (PATH_CHEAPEST_ARC ilk
çözüm + guided local search 2-opt/Or-opt iyileştirmesi, wall-clock
`time_limit` DEĞİL sabit bir `solution_limit` ile sınırlı — bkz.
"Determinism" bölümü). Cluster-second aşaması (gün bölme, açılış saatleri,
varış/kalkış zamanlaması, skor) burada YENİDEN yazılmıştır —
GreedyDistanceStrategy'den import edilmez, çünkü bu görevin kendi kısıtı o
dosyayı tamamen değişmeden bırakmayı gerektiriyor. Yalnızca saf, durumsuz
yardımcılar (haversine, HH:MM ayrıştırma/biçimlendirme, açılış-saati
ayrıştırma, kategori-bazlı ziyaret süresi tablosu) doğrudan oradan import
edilir — böylece alttaki matematik/sabitler iki strateji arasında asla
sessizce ayrışmaz; yalnızca gün-bölme akışının KONTROL YAPISI tekrarlanır,
ki bu zaten her stratejinin kendi "sıralama/zamanlama/gün dağılımı"
sorumluluğudur (bkz. RouteOptimizationStrategy'nin kendi docstring'i) —
OptimizationService'teki yetkilendirme/sahiplik/dedup/persistence/API
orkestrasyonuyla karıştırılmamalı (bu milestone'un "no business logic
duplication" kısıtı tam olarak o orkestrasyonu hedefliyor).

## Neden OR-Tools, elle yazılmış bir 2-opt değil

Bu milestone'un kendi hedefi "strateji soyutlamasının gerçekten
değiştirilebilir olduğunu kanıtlamak" — başka bir özel sezgisel yazmak yerine
gerçek, yaygın kullanılan bir kısıt çözücü entegre etmek bu iddianın çok daha
dürüst bir testi.

## Açık-yol (open path) TSP hilesi

OR-Tools'un RoutingIndexManager'ı her zaman bir "depo" (başlangıç/bitiş)
düğümü bekler. Burada gerçek bir depo yok — trip'in sabit bir başlangıç
noktası değeri yok, `GreedyDistanceStrategy` de böyle bir kavram taşımıyor.
Standart çözüm: sanal bir depo düğümü (indeks 0) ekleyip depoya/depodan tüm
kenarları 0 maliyetli yapmak — bu, "serbest başlangıç/bitiş"li açık bir yol
modeller (klasik OR-Tools "open VRP" hilesi), tek etkisi ardışık gerçek-durak
mesafelerinin toplamını minimize etmek, tıpkı bir TSP yolu gibi.

## Determinism

`solution_limit` (iyileştirici çözüm SAYISI) birincil durdurma koşulu —
makine hızından bağımsız, bu yüzden aynı girdi her zaman aynı sırayı üretir
(bkz. test_ortools_strategy.py'deki determinism testleri, ampirik olarak da
doğrulandı: aynı girdiyle 10 ardışık çağrı bit-bir-bit aynı sonucu verdi).
`time_limit` yalnızca patolojik derecede büyük girdilere karşı bir güvenlik
ağıdır (gezi boyutlarında — onlarca durak — hiç tetiklenmez, `solution_limit`
çok daha önce durdurur). GUIDED_LOCAL_SEARCH metasezgiseli rastgelelik
KULLANMAZ (simulated annealing'in aksine) — sabit sırayla komşuluk arar,
iyileştiren hamleleri kabul eder.

## Hard opening-hours time windows

Açılış saati bilgisi mevcut mekanlar için, açılış saatleri artık rota
SIRALAMASINI etkileyen SERT bir kısıt — önceki milestone'da yalnızca
son-işleme aşamasında (varışı açılışa kırp, kapanıştan sonraysa uyar ama
YENİDEN SIRALAMA yapma) kullanılıyordu. Bkz. `_solve_with_time_windows`.

**Model**: `_solve_distance_only`'nin aynı açık-yol modeline (sanal depo,
0-maliyetli depo kenarları) bir OR-Tools "Time" dimension eklenir —
kümülatif değişken, depodan itibaren dakika cinsinden geçen süreyi
(seyahat + ziyaret süresi) izler. Sanal aracın başlangıcı
`CumulVar(Start).SetRange(day_start, day_start)` ile `preferred_start_time`'a
sabitlenir. Açılış saati BİLİNEN her mekan için
`CumulVar(node).SetRange(open_minutes, close_minutes)` — sert bir alt/üst
sınır: solver, o düğüme varışın bu aralığın dışına düşeceği hiçbir sıralamayı
kabul etmez (gerekirse önce oraya erken varıp örtük biçimde "bekler" — dimension
slack'i bunu modeller, ayrı bir "bekleme" değişkenine gerek yoktur). Açılış
saati BİLİNMEYEN mekanlar `SetRange(0, HORIZON_MINUTES)` alır — pratikte
kısıtsız, yalnızca gerçek pencereli düğümlerin etrafında serbestçe
konumlandırılabilirler (spesifikasyonun 3. gereksinimi: "places without
opening-hours data must remain optimizable").

**Neden yalnızca gerçek pencere varken bu yola girilir**: `_solve_visit_order`
hiçbir mekanda kullanılabilir bir açılış saati yoksa (bugünkü üretim
verisinin neredeyse tamamı — bkz. docs "Assumptions") doğrudan
`_solve_distance_only`'ye düşer — bu, bir önceki milestone'un modeliyle
BİREBİR AYNI, sıfır davranış değişikliği (aynı test sonuçları, aynı
benchmark sayıları). Zaman dimension'ı yalnızca gerçekten en az bir sert
pencere varken modele eklenir.

### Impossible routes (eşzamanlı sağlanamayan pencereler)

İki veya daha fazla açılış-saati kısıtı AYNI ANDA sağlanamıyorsa (ör. birbirinden
çok uzak iki mekan, ikisi de yalnızca aynı dar sabah aralığında açık) —
`SolveWithParameters` bu durumda `None` döner (infeasible). Bu spesifikasyonun
kendi gereksinimi gereği ("do not silently produce an invalid itinerary"),
sonuç asla eksik/geçersiz bırakılmaz: `_solve_visit_order`, sert kısıtlar
olmadan `_solve_distance_only`'ye düşer (yine TÜM mekanları içeren, geçerli
bir itinerary) ve `optimize()` açıkça bir uyarı ekler — "sert zaman kısıtları
gevşetildi" — ardından mevcut son-işleme aşamasının kendi çakışma uyarıları
(değişmedi) hangi mekanların etkilendiğini tek tek listeler.

### Overnight/edge-time limitation

`_parse_opening_hours` (greedy'den import, DEĞİŞTİRİLMEDİ) gece-yarısını aşan
pencereleri ("22:00-02:00" gibi) doğru ayrıştırmıyor — `open_minutes >
close_minutes` gibi ters bir aralık döner. OR-Tools'a böyle bir aralığı
`CumulVar.SetRange` ile doğrudan vermek çöker (ampirik olarak doğrulandı: "CP
Solver fail" exception'ı). `_valid_hard_window` bu durumu tespit edip o TEK
düğüm için sert kısıtı ATLAR (mekan kısıtsız kabul edilir) — bu bir düğümün
kısıtını gevşetmek, `_solve_with_time_windows`'un TAMAMEN None dönmesinden
farklıdır. Mevcut yumuşak son-işleme çakışma uyarısı (değişmedi) yine de bu
mekan için tetiklenir, tıpkı greedy'de olduğu gibi — bu, "the current model"
zaten desteklemediği bir durum, bu milestone'un kapsamı `_parse_opening_hours`'u
düzeltmek değil (bkz. "Do not change GreedyDistanceStrategy").

### Performance protection

Sert-kısıtlı çözüm AYNI `SOLUTION_LIMIT`/`TIME_LIMIT_SECONDS` parametrelerini
kullanır — dimension eklemek arama uzayını büyütür ama durdurma koşulunu
DEĞİŞTİRMEZ. İmkansız bir durumda tek bir ek `_solve_distance_only` çağrısı
yapılır (kendi, ayrı `TIME_LIMIT_SECONDS` sınırıyla) — bu yüzden en kötü
durumda toplam solve süresi tek bir stratejinin `time_limit`'inin ~2 katını
geçmez (10s), yine de kesin biçimde SINIRLI — hiçbir sınırsız/tekrarlı arama
döngüsü yok. Gerçek gezi boyutlarında (bkz. test_large_place_set... ve yeni
determinism/performance testleri) her iki çağrı da milisaniyeler-saniyeler
içinde tamamlanır.
"""
from typing import Dict, List, Optional, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.domain.optimization.strategy import RouteOptimizationStrategy
from app.domain.optimization.models import (
    PlaceInput,
    OptimizationConstraints,
    OptimizedStop,
    OptimizedDay,
    OptimizationResult,
)
from app.infrastructure.optimization.greedy_distance_strategy import (
    haversine_km,
    _parse_hhmm,
    _format_minutes,
    _parse_opening_hours,
    _date_for,
    DEFAULT_VISIT_MINUTES,
    CATEGORY_VISIT_MINUTES,
    AVG_SPEED_KMH,
    LONG_SEGMENT_KM_THRESHOLD,
    FALLBACK_START,
    FALLBACK_END,
)

# ── Solver ayarları (bkz. modül docstring "Determinism" / "Performance protection") ──
SOLUTION_LIMIT = 200
TIME_LIMIT_SECONDS = 5
DISTANCE_SCALE = 1000  # km -> metre (OR-Tools tamsayı kenar maliyeti ister)

# ── Zaman dimension'ı ayarları (bkz. modül docstring "Hard opening-hours time windows") ──
# 14 gün — herhangi bir gerçekçi durak sayısı için cömert bir üst sınır
# (yüzlerce durak x saatlerce ziyaret bile bu sınırın çok altında kalır),
# ama CP çözücü için ihmal edilebilir boyutta bir tamsayı alanı.
HORIZON_MINUTES = 14 * 24 * 60
NO_WINDOW_RANGE = (0, HORIZON_MINUTES)


def _valid_hard_window(place: PlaceInput) -> Optional[Tuple[int, int]]:
    """Bu strateji tarafından SERT kısıt olarak uygulanabilir bir
    (open_minutes, close_minutes) döner — ayrıştırılamıyorsa VEYA gece-yarısını
    aşan (ters, open > close) bir pencereyse None (bkz. modül docstring
    "Overnight/edge-time limitation")."""
    parsed = _parse_opening_hours(place.opening_hours)
    if parsed is None:
        return None
    open_m, close_m = parsed
    if open_m > close_m:
        return None
    return open_m, close_m


def _solve_distance_only(places: List[PlaceInput]) -> List[PlaceInput]:
    """Saf mesafe-minimizasyonu açık-yol TSP'si — açılış saati kısıtı
    UYGULANMAZ. Bir önceki milestone'daki `_solve_visit_order` ile birebir
    aynı model/davranış (bkz. modül docstring "Neden yalnızca gerçek pencere
    varken bu yola girilir") — açılış saati verisi olmayan (bugün üretimdeki
    her durum) çağrılar için sıfır regresyon garantisi."""
    n = len(places)
    if n <= 2:
        return list(places)

    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == 0 or to_node == 0:
            return 0
        a, b = places[from_node - 1], places[to_node - 1]
        return int(round(haversine_km(a.lat, a.lng, b.lat, b.lng) * DISTANCE_SCALE))

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.solution_limit = SOLUTION_LIMIT
    search_parameters.time_limit.FromSeconds(TIME_LIMIT_SECONDS)

    solution = routing.SolveWithParameters(search_parameters)
    if solution is None:
        # Depo kenarları hep 0 maliyetli olduğundan pratikte imkansız — yine
        # de bir nedenden ötürü çözüm bulunamazsa girdi sırasına sessizce
        # düş. Hiçbir durağı kaybetmemek, en iyi sıralamayı bulmaktan önce
        # gelir (bkz. spesifikasyonun "fail gracefully" gereksinimi).
        return list(places)

    ordered: List[PlaceInput] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != 0:
            ordered.append(places[node - 1])
        index = solution.Value(routing.NextVar(index))
    return ordered


def _solve_with_time_windows(
    places: List[PlaceInput],
    day_start: int,
    hard_windows: Dict[int, Tuple[int, int]],
) -> Optional[List[PlaceInput]]:
    """`_solve_distance_only` ile aynı açık-yol mesafe modeli + bir "Time"
    dimension — `hard_windows`'taki indeksler (places listesindeki konum)
    kendi (open_minutes, close_minutes) aralığına SERTÇE kilitlenir, diğerleri
    `NO_WINDOW_RANGE` (kısıtsız) alır. Eşzamanlı sağlanamıyorsa `None` döner
    (bkz. modül docstring "Impossible routes")."""
    n = len(places)
    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == 0 or to_node == 0:
            return 0
        a, b = places[from_node - 1], places[to_node - 1]
        return int(round(haversine_km(a.lat, a.lng, b.lat, b.lng) * DISTANCE_SCALE))

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        service = 0 if from_node == 0 else CATEGORY_VISIT_MINUTES.get(
            places[from_node - 1].category, DEFAULT_VISIT_MINUTES
        )
        if from_node == 0 or to_node == 0:
            travel = 0
        else:
            a, b = places[from_node - 1], places[to_node - 1]
            travel = int(round((haversine_km(a.lat, a.lng, b.lat, b.lng) / AVG_SPEED_KMH) * 60))
        return service + travel

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    # slack_max == capacity == HORIZON_MINUTES: bir düğüme erken varıp
    # açılışını "beklemek" serbestçe mümkün olmalı (bkz. modül docstring) —
    # slack=0 bunu yasaklardı (varışı tam toplamda sabitler, bekleme yok).
    routing.AddDimension(time_callback_index, HORIZON_MINUTES, HORIZON_MINUTES, False, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")
    time_dimension.CumulVar(routing.Start(0)).SetRange(day_start, day_start)

    for idx in range(n):
        node_index = manager.NodeToIndex(idx + 1)
        open_m, close_m = hard_windows.get(idx, NO_WINDOW_RANGE)
        time_dimension.CumulVar(node_index).SetRange(open_m, close_m)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.solution_limit = SOLUTION_LIMIT
    search_parameters.time_limit.FromSeconds(TIME_LIMIT_SECONDS)

    solution = routing.SolveWithParameters(search_parameters)
    if solution is None:
        return None

    ordered: List[PlaceInput] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != 0:
            ordered.append(places[node - 1])
        index = solution.Value(routing.NextVar(index))
    return ordered


def _solve_visit_order(places: List[PlaceInput], day_start: int) -> Tuple[List[PlaceInput], bool]:
    """Sıralamayı çözer. İkinci eleman `hard_constraints_relaxed` — yalnızca
    en az bir sert pencere varken VE eşzamanlı sağlanamadığında True (bkz.
    modül docstring "Impossible routes"); bu durumda dönen sıra
    `_solve_distance_only`'nin ürettiği, mesafe-yalnızca sıradır (hiçbir
    durak kaybolmaz)."""
    n = len(places)
    if n <= 1:
        return list(places), False

    hard_windows = {
        idx: window
        for idx, place in enumerate(places)
        if (window := _valid_hard_window(place)) is not None
    }
    if not hard_windows:
        return _solve_distance_only(places), False

    ordered = _solve_with_time_windows(places, day_start, hard_windows)
    if ordered is not None:
        return ordered, False

    return _solve_distance_only(places), True


class ORToolsRouteOptimizationStrategy(RouteOptimizationStrategy):

    @property
    def name(self) -> str:
        return "ortools"

    def optimize(
        self,
        places: List[PlaceInput],
        constraints: OptimizationConstraints,
    ) -> OptimizationResult:
        if not places:
            return OptimizationResult(
                days=[], total_distance_km=0.0, total_travel_time_minutes=0.0,
                optimization_score=100.0, warnings=[],
            )

        try:
            day_start = _parse_hhmm(constraints.preferred_start_time)
            day_end = _parse_hhmm(constraints.preferred_end_time)
            if day_end <= day_start:
                raise ValueError
        except (ValueError, AttributeError):
            day_start, day_end = _parse_hhmm(FALLBACK_START), _parse_hhmm(FALLBACK_END)

        max_days = constraints.duration_days if (constraints.duration_days and constraints.duration_days >= 1) else None

        ordered, hard_constraints_relaxed = _solve_visit_order(places, day_start)
        n = len(ordered)

        # ── Cluster-second: GreedyDistanceStrategy.optimize ile aynı gün-
        # bölme/zamanlama kontrol akışı (bkz. modül docstring) — bilerek
        # yeniden yazıldı, import edilmedi.
        days: List[OptimizedDay] = []
        warnings: List[str] = []
        missing_hours_names: List[str] = []
        overflow_warned = False

        if hard_constraints_relaxed:
            # bkz. modül docstring "Impossible routes" — en az iki açılış
            # saati kısıtı eşzamanlı sağlanamadı, mesafe-yalnızca sıraya
            # düşüldü. Aşağıdaki döngü yine de hangi mekan(lar)ın çakıştığını
            # tek tek işaretleyecek (mevcut, değişmemiş yumuşak kontrol).
            warnings.append(
                "Bazı mekanların açılış saatleri birbiriyle uyumsuz olduğu için "
                "sabit zaman kısıtları gevşetildi; rota yalnızca mesafeye göre "
                "sıralandı."
            )

        day_index = 0
        current_time = day_start
        current_day_stops: List[OptimizedStop] = []
        total_distance = 0.0
        total_travel_minutes = 0.0

        def flush_day() -> None:
            nonlocal day_index, current_time, current_day_stops
            if current_day_stops:
                days.append(OptimizedDay(
                    day_index=day_index,
                    date=_date_for(constraints.start_date, day_index),
                    stops=current_day_stops,
                ))
                day_index += 1
            current_day_stops = []
            current_time = day_start

        i = 0
        while i < n:
            place = ordered[i]
            forced_last_day = max_days is not None and day_index >= max_days - 1
            arrival = current_time

            open_close = _parse_opening_hours(place.opening_hours)
            if open_close is None:
                if place.opening_hours is None:
                    missing_hours_names.append(place.name)
            else:
                open_m, close_m = open_close
                if arrival < open_m:
                    arrival = open_m  # açılışı bekle — sessizce
                if arrival >= close_m:
                    warnings.append(
                        f"{place.name}: planlanan varış saati belirtilen çalışma saatleriyle çakışıyor"
                    )

            visit_minutes = CATEGORY_VISIT_MINUTES.get(place.category, DEFAULT_VISIT_MINUTES)
            departure = arrival + visit_minutes

            if current_day_stops and not forced_last_day and departure > day_end:
                flush_day()
                continue  # aynı durağı temiz bir günde yeniden dene

            if forced_last_day and departure > day_end and not overflow_warned:
                warnings.append(
                    "İstenen gün sayısına sığmayan duraklar son güne eklendi (zaman bütçesi aşıldı)."
                )
                overflow_warned = True

            stop = OptimizedStop(
                place_id=place.place_id, name=place.name, lat=place.lat, lng=place.lng,
                day_index=day_index, order_index=len(current_day_stops),
                arrival_time=_format_minutes(arrival), departure_time=_format_minutes(departure),
                visit_duration_minutes=visit_minutes,
            )
            current_day_stops.append(stop)
            current_time = departure

            if i + 1 < n:
                nxt = ordered[i + 1]
                dist = haversine_km(place.lat, place.lng, nxt.lat, nxt.lng)
                travel_minutes = (dist / AVG_SPEED_KMH) * 60
                stop.travel_distance_to_next_km = round(dist, 2)
                stop.travel_time_to_next_minutes = round(travel_minutes, 1)
                total_distance += dist
                total_travel_minutes += travel_minutes
                if dist >= LONG_SEGMENT_KM_THRESHOLD:
                    warnings.append(
                        f"{place.name} → {nxt.name}: uzun bir seyahat segmenti ({round(dist)} km)"
                    )
                current_time += travel_minutes

            i += 1

        flush_day()

        if missing_hours_names:
            warnings.append(
                f"Açılış saatleri bilinmiyor: {len(missing_hours_names)} mekan için "
                "program bu kısıt dikkate alınmadan oluşturuldu."
            )

        avg_km = (total_distance / (n - 1)) if n > 1 else 0.0
        travel_penalty = min(40.0, avg_km * 2)
        warning_penalty = min(30.0, len(warnings) * 5)
        score = round(max(0.0, 100.0 - travel_penalty - warning_penalty), 1)

        return OptimizationResult(
            days=days,
            total_distance_km=round(total_distance, 2),
            total_travel_time_minutes=round(total_travel_minutes, 1),
            optimization_score=score,
            warnings=warnings,
        )
