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
orkestrasyonuyla karıştırılmamalı.

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
makine hızından bağımsız, bu yüzden aynı girdi her zaman aynı sırayı üretir.
`time_limit` yalnızca patolojik derecede büyük girdilere karşı bir güvenlik
ağıdır. GUIDED_LOCAL_SEARCH metasezgiseli rastgelelik KULLANMAZ (simulated
annealing'in aksine) — sabit sırayla komşuluk arar, iyileştiren hamleleri
kabul eder. Gün-farkında çok-günlü döngü de (aşağıya bkz.) bu özelliği miras
alır: her günün kendi solve çağrısı deterministiktir, ve günler SIRAYLA
(rastgele değil) çözüldüğünden tüm döngü de deterministiktir.

## Hard opening-hours time windows — day-aware

Açılış saati bilgisi mevcut mekanlar için, açılış saatleri rota
SIRALAMASINI etkileyen SERT bir kısıt — yalnızca son-işleme aşamasında
kırpılan/uyarılan yumuşak bir sinyal değil. **Bu kısıt artık GÜN-FARKINDA
değerlendiriliyor** — bir önceki milestone'un tek-sürekli-zaman-çizelgesi
modelinin kusurunu (aşağıya bkz. "Day-aware scheduling → The single-
continuous-timeline bug") kapatıyor.

### Day-aware scheduling

**Model**: `_solve_distance_only`'nin aynı açık-yol modeli (sanal depo,
0-maliyetli depo kenarları) — ama artık TEK bir sürekli zaman çizelgesi
üzerinde DEĞİL, GÜN BAŞINA ayrı ayrı çözülüyor (`_solve_day`,
`_solve_day_aware_schedule` tarafından döngüsel çağrılır):

- Her günün kendi TAZE bir OR-Tools "Time" dimension'ı var — kapasitesi
  o günün kendi bütçesi (`day_end - day_start`), `fix_start_cumul_to_zero=True`
  ile 0 = O GÜNÜN `day_start`'ı (dünün kümülatif zamanından bağımsız).
  Bu, bir sert pencerenin SetRange'i artık gerçekten "bugünün saat kaçı"
  sorusuna karşı kontrol ediliyor demek — dünden miras kalan, alakasız bir
  sayıya karşı değil.
- Açılış saati BİLİNEN bir mekan için pencere `day_start/day_end`'e göre
  GÜNE-GÖRELİ dakikalara çevrilir (`open_minutes - day_start` vb., [0,
  day_budget] aralığına kırpılır) ve `CumulVar(node).SetRange(...)` ile
  sertçe uygulanır — HANGİ güne denk gelirse gelsin, aynı (deterministik)
  çeviri kullanılır, çünkü `preferred_start_time`/`preferred_end_time` her
  gün İÇİN AYNI (bkz. docs "Assumptions: opening hours are daily-only").
- Açılış saati BİLİNMEYEN (veya bu güne hiç sığmayan — aşağıya bkz.)
  mekanlar `SetRange(0, day_budget)` alır — o günün kısıtsız serbest
  aralığı, sert pencereli mekanların ETRAFINA konumlandırılabilirler
  (spesifikasyonun 3. gereksinimi).
- Her mekan `AddDisjunction([node], DISJUNCTION_PENALTY)` ile o gün için
  OPSİYONELDİR (istisna: zorunlu son gün — aşağıya bkz.) — solver'ın
  KENDİSİ "bugüne kim sığar, kim yarına kalır" kararını verir; elle
  yazılmış bir "taşma tespit et → günü kapat → aynı durağı yeniden dene"
  döngüsüne (önceki modelin kusurunun asıl kaynağı) hiç gerek kalmaz.
  `DISJUNCTION_PENALTY`, gerçekçi HERHANGİ bir günlük rota mesafesinden kat
  kat büyük — solver bir mekanı yalnızca zaman bütçesi/penceresi GERÇEKTEN
  izin vermediğinde düşürür, asla salt mesafe tasarrufu için değil.

Bu, spesifikasyonun kendi "Do not introduce vehicle-routing complexity
unless the current architecture genuinely requires it" kısıtına saygılı,
en küçük doğru model: TEK araçlı model KORUNUYOR (çoklu-araç/vardiya
kavramı yok), yalnızca AYNI modelin gün başına TEKRAR TEKRAR (her seferinde
taze bir saatle) çağrılması yoluyla gün-farkındalık kazandırılıyor.

### The single-continuous-timeline bug (bir önceki milestone'da)

Bir önceki milestone'un `_solve_with_time_windows`'u TEK bir zaman
dimension'ı kullanıyordu — `day_start`'tan başlayıp trip boyunca hiç
sıfırlanmadan büyüyen bir saat. Gün bölme ise TAMAMEN AYRI bir son-işleme
adımıydı (mevcut yürüyüş). Bu iki mekanizma birbirinden HABERSİZDİ:
solver'ın "sert kısıt sağlandı" kararı HAM, sınırsız kümülatif dakikalara
karşı veriliyordu — o mekanın GERÇEKTE hangi güne düştüğüne ve o günün
KENDİ yerel saatine karşı değil.

Matematiksel olarak kanıtlanabilir ki (ve ampirik olarak doğrulandı):
gerçek gün-yerel varış her zaman <= solver'ın ham kümülatif değeri (gün
sıfırlamaları zamanı yalnızca AZALTABİLİR, hiç artıramaz) — bu yüzden bu
kusur asla "solver OK dedi ama gerçek varış kapanıştan SONRAYA düştü"
biçiminde SESSİZCE ortaya çıkamaz (mevcut yumuşak kontrol erken varışları
sessizce açılışa kırptığı için, geç yönde sapma hep görünür bir uyarıya
dönüşürdü zaten). Asıl gözlemlenen, doğrulanan kusur şuydu:

**Aynı dar pencereyi paylaşan, coğrafi olarak birbirinden uzak iki mekan**
(ör. ikisi de yalnızca 09:00-09:30 açık, aralarında saatlerce sürecek bir
mesafe) — gün-farkında doğru cevap trivial: birini 1. güne, diğerini 2.
güne koy, ikisi de KENDİ gününün 09:00'ında açılışta karşılanır. Eski model
bunu KÜRESEL OLARAK İMKANSIZ sanıyordu (ikisi de aynı sınırsız hamsaatin
aynı dilimi için yarışıyordu) ve HER İKİ sert kısıtı da tamamen atıp
mesafe-yalnızca'ya düşüyordu — gün-farkında bir modelin ikisini de kusursuzca
karşılayabileceği bir durumda. Ayrıca, o düşme (relaxation) yolunun KENDİ
yürüyüşünde de bağımsız bir "bayat varış" kusuru tespit edildi: gün-taşması
tespit edilip `flush_day()+continue` ile aynı durak yeniden denenmeden ÖNCE,
açılış-saati çakışma kontrolü flush-ÖNCESİ (dünden miras, alakasız) `arrival`
değeriyle çalıştırılıyor ve `warnings`'e GERİ ALINAMAZ biçimde ekleniyordu —
gerçek (flush-sonrası) varış tam zamanında olsa bile sahte bir "çakışıyor"
uyarısı üretebiliyordu. Bu yeni day-aware modelde bu kusurun HİÇBİRİ artık
mümkün değil — her günün gerçek yerel saatine karşı, o günün KENDİ solve
çağrısında, YAPISAL OLARAK doğru kontrol ediliyor, tahmin/tesadüf değil.
`test_ortools_strategy.py`'deki
`test_two_incompatible_same_window_places_satisfied_across_separate_days`
bu tam senaryoyu (spesifikasyonun 8. "critical regression test"
gereksinimi) hem eski modelin kusurunu hem yeni modelin düzeltmesini
doğrudan kanıtlıyor.

### Impossible routes (day-aware)

Bir mekanın penceresi `day_start`/`day_end` ile HİÇ örtüşmüyorsa (ör.
pencere günün tamamı kapandıktan sonra başlıyor) — bu, HANGİ güne
konursa konsun asla karşılanamaz (her gün AYNI `day_start`/`day_end`'i
paylaştığından). Bu tür mekanlar baştan tespit edilip sert kısıtsız kabul
edilir. Ayrıca, ZORUNLU SON GÜNDE (bkz. aşağı) kalan mekanların pencereleri
eşzamanlı sağlanamıyorsa, o gün mesafe-yalnızca'ya düşer. Her iki durumda
da: hiçbir mekan kaybolmaz, ve `optimize()` açıkça bir uyarı ekler — "sert
zaman kısıtları gevşetildi."

### Day boundaries — zorunlu son gün

`duration_days` verildiyse, SON izin verilen gün (`day_index == max_days-1`)
ZORUNLUDUR — o güne kadar hâlâ kalan TÜM mekanlar, bütçeye sığsın sığmasın,
o güne eklenir (`AddDisjunction` KULLANILMAZ) — mevcut "forced_last_day"
davranışıyla birebir aynı, tek seferlik bir "sığmayan duraklar... eklendi"
uyarısıyla. `duration_days` verilmediyse gün sayısı kendiliğinden türer —
tüm mekanlar planlanana kadar (veya `len(places)` güvenlik sınırına
ulaşılana kadar — pratikte hiç tetiklenmez) döngü devam eder.

### Overnight/edge-time limitation

`_parse_opening_hours` (greedy'den import, DEĞİŞTİRİLMEDİ) gece-yarısını
aşan pencereleri ("22:00-02:00" gibi) doğru ayrıştırmıyor. `_valid_hard_window`
bu durumu tespit edip o mekan için sert kısıtı ATLAR — bu, her gün için
ayrı ayrı geçerli, davranış önceki milestone'la aynı.

### Performance protection

Her günün solve'u AYNI `SOLUTION_LIMIT`/`TIME_LIMIT_SECONDS`'a tabi —
gün-farkında döngü sınırsız aramaya YOL AÇMAZ, yalnızca AYNI sınırlı
işlemi gün sayısı kadar tekrarlar. Gerçek gezi boyutlarında (bkz.
Verification → Benchmark) toplam süre milisaniyeler-birkaç saniye arasında
kalır; performans etkisi doğrudan ölçülüp docs/trip-optimizer.md'de
belgelenmiştir.
"""
from typing import Dict, List, Optional, Set, Tuple

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

# Bir mekanı bir günden düşürmenin "maliyeti" (bkz. modül docstring "Day-aware
# scheduling") — DISTANCE_SCALE birimlerinde (metre), gerçekçi HERHANGİ bir
# günlük rota mesafesinden (binlerce km bile olsa) kat kat büyük.
DISJUNCTION_PENALTY = 100_000_000


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


def _window_overlaps_day(window: Tuple[int, int], day_start: int, day_end: int) -> bool:
    """Bir pencere `[day_start, day_end]` ile HİÇ örtüşmüyorsa (ör. mekan
    günün tamamı kapandıktan sonra açılıyor) — bu HANGİ güne konursa konsun
    asla karşılanamaz, çünkü her gün AYNI day_start/day_end'i paylaşır (bkz.
    modül docstring "Impossible routes")."""
    open_m, close_m = window
    return not (close_m < day_start or open_m > day_end)


def _solve_distance_only(places: List[PlaceInput]) -> List[PlaceInput]:
    """Saf mesafe-minimizasyonu açık-yol TSP'si — açılış saati kısıtı
    UYGULANMAZ. Hem (a) hiçbir mekanda kullanılabilir açılış saati yokken
    TEK geçişlik global sıralama için, hem de (b) day-aware döngüde bir
    günün sert kısıtları eşzamanlı sağlanamadığında o günün gevşetilmiş
    (mesafe-yalnızca) sıralaması için kullanılır — bkz. modül docstring
    "Impossible routes"."""
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


def _solve_day(
    remaining: List[PlaceInput],
    day_start: int,
    day_end: int,
    mandatory: bool,
    unconstrained_ids: Set[int],
) -> Optional[Tuple[List[PlaceInput], List[PlaceInput]]]:
    """Tek bir GÜNÜN açık-yol TSP + zaman-penceresi modelini çözer —
    `_solve_distance_only` ile aynı temel model (sanal depo, 0-maliyetli
    depo kenarları), ama "Time" dimension'ı BU GÜNE ÖZGÜ taze bir saatle
    başlar: kapasite = `day_end - day_start`, `fix_start_cumul_to_zero=True`
    ile 0 = bu günün `day_start`'ı (bkz. modül docstring "Day-aware
    scheduling").

    `mandatory=False` iken her mekan `AddDisjunction` ile OPSİYONELDİR
    (büyük bir ceza karşılığında düşürülebilir) — solver'ın kendisi "bugüne
    kim sığar" kararını verir. `mandatory=True` (zorunlu son gün) tüm
    mekanlar ZORUNLUDUR — mevcut "forced_last_day" davranışıyla birebir
    aynı, hiçbir yer düşmez.

    `unconstrained_ids`: bu day_start/day_end ile HİÇBİR günde asla
    karşılanamayacak (bkz. `_window_overlaps_day`) mekanların place_id'leri —
    bunlar için sert kısıt hiç uygulanmaz.

    Döner: (bugün ziyaret edilenler sırayla, yarına kalanlar) —
    `mandatory=True` iken eşzamanlı sağlanamazsa `None`."""
    n = len(remaining)
    if n == 0:
        return [], []

    day_budget = day_end - day_start

    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == 0 or to_node == 0:
            return 0
        a, b = remaining[from_node - 1], remaining[to_node - 1]
        return int(round(haversine_km(a.lat, a.lng, b.lat, b.lng) * DISTANCE_SCALE))

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        service = 0 if from_node == 0 else CATEGORY_VISIT_MINUTES.get(
            remaining[from_node - 1].category, DEFAULT_VISIT_MINUTES
        )
        if from_node == 0 or to_node == 0:
            travel = 0
        else:
            a, b = remaining[from_node - 1], remaining[to_node - 1]
            travel = int(round((haversine_km(a.lat, a.lng, b.lat, b.lng) / AVG_SPEED_KMH) * 60))
        return service + travel

    # Dimension kapasitesi day_budget'a SIKI SIKIYA bağlı DEĞİL — bilerek
    # cömert (bkz. aşağıdaki EXIT_CAP açıklaması). Her GERÇEK düğümün kendi
    # CumulVar'ı (varış zamanı) ayrı ayrı [0, day_budget] veya sert pencereye
    # sabitlenir; kapasite yalnızca bir üst güvenlik sınırı.
    exit_cap = day_budget + max(CATEGORY_VISIT_MINUTES.values(), default=DEFAULT_VISIT_MINUTES) + DEFAULT_VISIT_MINUTES

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(time_callback_index, exit_cap, exit_cap, True, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")

    # EXIT (depoya dönüş) geçişi, en son ziyaret edilen düğümün KENDİ ziyaret
    # süresini "üstlenir" (bkz. time_callback: from_node==gerçek düğümse
    # service dahil edilir) — bu yüzden depo/EXIT'in kendi CumulVar'ı
    # day_budget'a değil, cömert `exit_cap`'e bırakılmalı. Aksi halde, TEK
    # başına bile day_budget'ı aşan bir ziyaret süresine sahip bir mekan
    # (ör. günün TEK durağı) yapay biçimde infeasible görünür — mevcut
    # "tek durak günü aşabilir" kuralının (bkz. GreedyDistanceStrategy'nin
    # aynı davranışı) bu modeldeki karşılığı budur.
    time_dimension.CumulVar(routing.End(0)).SetRange(0, exit_cap)

    for idx, place in enumerate(remaining):
        node_index = manager.NodeToIndex(idx + 1)
        window = None if place.place_id in unconstrained_ids else _valid_hard_window(place)
        if window is not None:
            open_m, close_m = window
            rel_open = max(0, open_m - day_start)
            rel_close = min(day_budget, close_m - day_start)
            time_dimension.CumulVar(node_index).SetRange(rel_open, rel_close)
        else:
            time_dimension.CumulVar(node_index).SetRange(0, day_budget)

        if not mandatory:
            routing.AddDisjunction([node_index], DISJUNCTION_PENALTY)

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

    visited_positions: Set[int] = set()
    ordered: List[PlaceInput] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != 0:
            pos = node - 1
            ordered.append(remaining[pos])
            visited_positions.add(pos)
        index = solution.Value(routing.NextVar(index))

    leftover = [p for pos, p in enumerate(remaining) if pos not in visited_positions]
    return ordered, leftover


def _solve_day_aware_schedule(
    places: List[PlaceInput],
    day_start: int,
    day_end: int,
    max_days: Optional[int],
) -> Tuple[List[List[PlaceInput]], bool]:
    """Açılış saatlerini GÜN-FARKINDA sert kısıt olarak uygulayan çok-günlü
    çözücü döngüsü (bkz. modül docstring "Day-aware scheduling"). Her gün
    `_solve_day` ile KENDİ taze [0, day_budget] saatiyle ayrı ayrı çözülür —
    bu, tek-sürekli-zaman-çizelgesi kusurunu YAPISAL OLARAK ortadan kaldırır.

    Döner: (day_groups, hard_constraints_relaxed). `day_groups[i]` i.
    günün ziyaret sırasıdır (PlaceInput listesi). `hard_constraints_relaxed`
    yalnızca en az bir mekanın penceresi hiçbir günde/gün-içi
    karşılanamadığında True olur."""
    day_budget = day_end - day_start

    # Bu day_start/day_end ile HİÇBİR günde asla karşılanamayacak pencereler
    # (her gün AYNI pencere tekrarlandığından — bkz. docs "Assumptions:
    # opening hours are daily-only" — bugün karşılanamıyorsa yarın da
    # karşılanamaz) baştan tespit edilip gevşetilir.
    unconstrained_ids: Set[int] = set()
    for place in places:
        window = _valid_hard_window(place)
        if window is not None and not _window_overlaps_day(window, day_start, day_end):
            unconstrained_ids.add(place.place_id)

    relaxed = bool(unconstrained_ids)

    remaining = list(places)
    day_groups: List[List[PlaceInput]] = []
    max_iterations = max_days if max_days is not None else len(places)
    day_index = 0

    while remaining and day_index < max_iterations:
        is_final = day_index == max_iterations - 1
        result = _solve_day(remaining, day_start, day_end, mandatory=is_final, unconstrained_ids=unconstrained_ids)

        if result is None:
            # Yalnızca is_final=True iken olur (bkz. modül docstring
            # "Impossible routes") — bu günün kalan mekanları eşzamanlı
            # sağlanamadı. Sert kısıtsız (mesafe-yalnızca) çöz, kalan
            # HERKESİ bu güne ekle — hiçbir mekan kaybolmaz.
            visited, leftover = _solve_distance_only(remaining), []
            relaxed = True
        else:
            visited, leftover = result
            if not visited and remaining:
                # Solver hiçbir mekanı dahil etmedi (hepsi opsiyonel olarak
                # düşürüldü) — ilerleme sağlanamıyor, sıkışma önleme.
                visited, leftover = _solve_distance_only(remaining), []
                relaxed = True

        day_groups.append(visited)
        remaining = leftover
        day_index += 1

    if remaining:
        # Güvenlik ağı — yukarıdaki dallar `remaining`'i hep tükettiği için
        # pratikte hiç tetiklenmemeli, ama hiçbir mekanı asla kaybetmemek
        # için: kalanları son bir ekstra güne zorla ekle.
        day_groups.append(_solve_distance_only(remaining))
        relaxed = True

    return day_groups, relaxed


def _walk_day_groups(
    day_groups: List[List[PlaceInput]],
    day_start: int,
    day_end: int,
    max_days: Optional[int],
    start_date: Optional[str],
) -> Tuple[List[OptimizedDay], List[str], float, float]:
    """`day_groups` (zaten day-aware çözücü tarafından doğru günlere
    bölünmüş) üzerinde TEK bir geçişte yürür — eski modelin "taşma tespit
    et → günü kapat → aynı durağı yeniden dene" mantığına GEREK YOK, çünkü
    gün sınırları zaten `_solve_day_aware_schedule` tarafından doğru
    biçimde belirlendi. Bu da eski modeldeki "bayat varış" kusurunu
    (bkz. modül docstring) yapısal olarak ortadan kaldırır: her durağın
    açılış-saati kontrolü, o durağın GERÇEK (bu geçişte hesaplanan) varış
    değeriyle, tam bir kez çalışır."""
    days: List[OptimizedDay] = []
    warnings: List[str] = []
    missing_hours_names: List[str] = []
    overflow_warned = False
    total_distance = 0.0
    total_travel_minutes = 0.0

    flat: List[Tuple[int, PlaceInput]] = [
        (day_idx, place) for day_idx, group in enumerate(day_groups) for place in group
    ]
    n = len(flat)
    if n == 0:
        return days, warnings, total_distance, total_travel_minutes

    current_day_stops: List[OptimizedStop] = []
    active_day_idx = flat[0][0]
    current_time = day_start

    for i, (day_idx, place) in enumerate(flat):
        if day_idx != active_day_idx:
            if current_day_stops:
                days.append(OptimizedDay(
                    day_index=active_day_idx,
                    date=_date_for(start_date, active_day_idx),
                    stops=current_day_stops,
                ))
            current_day_stops = []
            active_day_idx = day_idx
            current_time = day_start

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

        forced_last_day = max_days is not None and day_idx >= max_days - 1
        if forced_last_day and departure > day_end and not overflow_warned:
            warnings.append(
                "İstenen gün sayısına sığmayan duraklar son güne eklendi (zaman bütçesi aşıldı)."
            )
            overflow_warned = True

        stop = OptimizedStop(
            place_id=place.place_id, name=place.name, lat=place.lat, lng=place.lng,
            day_index=day_idx, order_index=len(current_day_stops),
            arrival_time=_format_minutes(arrival), departure_time=_format_minutes(departure),
            visit_duration_minutes=visit_minutes,
        )
        current_day_stops.append(stop)
        current_time = departure

        if i + 1 < n:
            next_day_idx, nxt = flat[i + 1]
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
            if next_day_idx == day_idx:
                current_time += travel_minutes
            # farklı günse: current_time bir sonraki iterasyonun başında
            # zaten day_start'a resetlenecek.

    if current_day_stops:
        days.append(OptimizedDay(
            day_index=active_day_idx,
            date=_date_for(start_date, active_day_idx),
            stops=current_day_stops,
        ))

    if missing_hours_names:
        warnings.append(
            f"Açılış saatleri bilinmiyor: {len(missing_hours_names)} mekan için "
            "program bu kısıt dikkate alınmadan oluşturuldu."
        )

    return days, warnings, total_distance, total_travel_minutes


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

        has_hard_windows = any(_valid_hard_window(p) is not None for p in places)

        if has_hard_windows:
            # ── Day-aware yol (bkz. modül docstring "Day-aware scheduling") ──
            day_groups, hard_constraints_relaxed = _solve_day_aware_schedule(
                places, day_start, day_end, max_days
            )
            days, warnings, total_distance, total_travel_minutes = _walk_day_groups(
                day_groups, day_start, day_end, max_days, constraints.start_date
            )
            if hard_constraints_relaxed:
                warnings.insert(
                    0,
                    "Bazı mekanların açılış saatleri birbiriyle uyumsuz olduğu için "
                    "sabit zaman kısıtları gevşetildi; rota yalnızca mesafeye göre "
                    "sıralandı."
                )
            n = sum(len(g) for g in day_groups)

        else:
            # ── Sert pencere yok: önceki milestone'un modeliyle BİREBİR
            # AYNI, DEĞİŞTİRİLMEMİŞ tek-geçişlik yol — sıfır davranış
            # değişikliği (bkz. modül docstring "Day-aware scheduling").
            ordered = _solve_distance_only(places)
            n = len(ordered)

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
