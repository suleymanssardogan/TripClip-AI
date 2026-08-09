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
"""
from typing import List

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

# ── Solver ayarları (bkz. modül docstring "Determinism") ────────────────────
SOLUTION_LIMIT = 200
TIME_LIMIT_SECONDS = 5
DISTANCE_SCALE = 1000  # km -> metre (OR-Tools tamsayı kenar maliyeti ister)


def _solve_visit_order(places: List[PlaceInput]) -> List[PlaceInput]:
    """OR-Tools ile açık-yol TSP sırası. n<=2 için sıralama kararı yoktur
    (tüm permütasyonlar eşdeğer — mesafe simetrik), solver hiç devreye
    girmeden kısa devre yapılır."""
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

        ordered = _solve_visit_order(places)
        n = len(ordered)

        # ── Cluster-second: GreedyDistanceStrategy.optimize ile aynı gün-
        # bölme/zamanlama kontrol akışı (bkz. modül docstring) — bilerek
        # yeniden yazıldı, import edilmedi.
        days: List[OptimizedDay] = []
        warnings: List[str] = []
        missing_hours_names: List[str] = []
        overflow_warned = False

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
