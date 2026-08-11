"""
Infrastructure katmanı — v1 route optimization stratejisi: greedy nearest-
neighbor + "route-first, cluster-second" gün bölme.

Bilinçli olarak `app/ml/route_optimizer.py`'yi (Video pipeline'ın TSP
çözücüsü) YENİDEN KULLANMIYOR — mimari kısıt "optimizer'ı video işleme/
semantic search/place extraction'dan bağımsız tut" (bkz.
docs/trip-optimizer.md "Architecture") `app/ml`'e (pipeline paketi) bir
bağımlılık açmayı engelliyor. Haversine + nearest-neighbor'ın burada ~15
satır tekrarı, iki bounded context'i birbirine bağlamaktan daha ucuz bir
bedel.

Algoritma (bkz. docs/trip-optimizer.md "Algorithm" için tam açıklama):
1. Route-first: TÜM seçili mekanlar üzerinde tek bir nearest-neighbor
   rotası çıkar (gün ayrımı yapılmadan) — coğrafi olarak yakın mekanlar
   doğal olarak art arda gelir, bu da çoklu şehir senaryolarında bile
   "yakın mekanları grupla" gereksinimini basitçe karşılar.
2. Cluster-second: bu tek rotayı, preferred_start_time/end_time'dan türeyen
   günlük zaman bütçesine göre açgözlü biçimde günlere böler. Bir durak o
   günün bütçesine sığmıyorsa yeni bir gün açılır (duration_days
   verilmediyse gün sayısı böyle kendiliğinden türer).
3. Açılış saatleri (varsa) sıralı zaman ilerleyişini etkiler: varış açılıştan
   önceyse varış açılışa ertelenir (sessizce — bu "saatlere uymak"tır);
   varış kapanıştan sonraysa bir uyarı eklenir ama v1 duraklar arasında
   yeniden dağıtım YAPMAZ (bkz. Limitations — bu tam bir kısıt çözücünün
   işi, ileride bir OR-Tools stratejisinin doğal genişleme noktası).

## Overnight Time Ranges (Req: gece yarısını aşan planlama/açılış pencereleri)

Hem `preferred_start_time`/`preferred_end_time` (planlama penceresi) hem de
bir mekanın `opening_hours`'ı (açılış penceresi) gece yarısını AŞABİLİR —
`"18:00-01:00"`, `"22:00-02:00"` gibi. Semantik kural (bkz.
docs/trip-optimizer.md "Overnight Time Ranges") basit ve HER İKİ tür pencere
için AYNI:

    start <= end  → aynı-gün aralığı
    start >  end  → gece yarısını aşan (overnight) aralık

Eşit `start == end` HÂLÂ geçersiz kabul edilir (mevcut sözleşme — bkz.
`OptimizationService._validate_hhmm` çağıranı — DEĞİŞMEDİ, yalnızca "eşitsiz
her ikisi de kabul" yönünde genişletildi, "eşit → geçerli" YÖNÜNDE değil).

Bu modülün SÜREKLİ (gece yarısını aşabilen, monotonik) zaman ekseni
temsili — `MINUTES_PER_DAY`, `PlanningTimeWindow`, ve alttaki yardımcı
fonksiyonlar — hem bu strateji hem `ortools_strategy.py` (buradan import
eder) tarafından PAYLAŞILIYOR; bu, iki stratejinin "aynı gün+açılış-saati
GİRDİSİNİ AYNI ŞEKİLDE yorumlaması" gereksinimini (bkz. modül docstring'i,
ortools_strategy.py) kodun KENDİSİNDE, yorumla değil, garanti eder.

Zaman dilimi desteği YOK ve eklenmedi — bir overnight aralık, saat
dilimsiz, salt yerel bir "planlama saati" kavramıdır (bkz.
docs/trip-optimizer.md "Timezone").
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.domain.optimization.strategy import RouteOptimizationStrategy
from app.domain.optimization.models import (
    PlaceInput,
    OptimizationConstraints,
    OptimizedStop,
    OptimizedDay,
    OptimizationResult,
)

# ── Sabitler (bkz. docs/trip-optimizer.md "Assumptions") ────────────────────

DEFAULT_VISIT_MINUTES = 60
CATEGORY_VISIT_MINUTES = {
    "museum": 90,
    "landmark": 30,
    "restaurant": 60,
    "park": 45,
    "viewpoint": 20,
    "shopping": 45,
}
AVG_SPEED_KMH = 25.0          # şehir-içi ortalama (trafik/ışıklar dahil) — gerçek bir routing motoru yok
LONG_SEGMENT_KM_THRESHOLD = 50.0  # bu eşiği aşan ardışık durak mesafesi muhtemelen şehirler-arası bir sıçrama
FALLBACK_START = "09:00"
FALLBACK_END = "18:00"

# Gün başına dakika — bu tek sabit, "24 * 60" bu modülde/ortools_strategy.py'de
# BAŞKA HİÇBİR YERDE elle tekrarlanmaz (bkz. "Overnight Time Ranges" bölümü,
# Req 9 "do not hardcode 24*60 assumptions in multiple places").
MINUTES_PER_DAY = 24 * 60


def _parse_hhmm(raw: str) -> int:
    """'HH:MM' → gece yarısından itibaren dakika."""
    h, m = raw.split(":")
    return int(h) * 60 + int(m)


def _format_minutes(total_minutes: float) -> str:
    """SÜREKLİ (gece yarısını aşabilen, `MINUTES_PER_DAY`'den büyük olabilen)
    bir dakika değerini `"HH:MM"` duvar-saatine çevirir — `%` işlemi zaten
    doğru şekilde geri sarıyor (ör. 1500 → "01:00"), overnight bir varış için
    ekstra bir dönüşüme gerek yok (bkz. "Overnight Time Ranges")."""
    wrapped = int(round(total_minutes)) % MINUTES_PER_DAY
    return f"{wrapped // 60:02d}:{wrapped % 60:02d}"


def _parse_opening_hours(raw: Optional[str]) -> Optional[Tuple[int, int]]:
    """'09:00-18:00' → (540, 1080), '22:00-02:00' → (1320, 120) — HER İKİSİ
    de aynı şekilde, HAM (open_minutes, close_minutes) çifti olarak
    döner; overnight olup olmadığına (open > close) burada bakılmaz/hiçbir
    şey reddedilmez (bkz. "Overnight Time Ranges" — yorumlama alttaki
    `_day_relative_window`/`_resolve_arrival`'ın işi, ayrıştırma değil).
    Ayrıştırılamayan/eksik değer None döner — 'bilinmiyor' ile aynı
    şekilde ele alınır (bkz. modül docstring'i)."""
    if not raw:
        return None
    try:
        open_s, close_s = raw.split("-")
        return _parse_hhmm(open_s.strip()), _parse_hhmm(close_s.strip())
    except (ValueError, AttributeError):
        return None


@dataclass(frozen=True)
class PlanningTimeWindow:
    """`preferred_start_time`/`preferred_end_time`'dan türeyen günlük
    planlama penceresi — SÜREKLİ bir zaman ekseninde ifade edilir.
    `end_minutes` HER ZAMAN `start_minutes`'e eşit ya da ondan büyüktür
    (`is_overnight` iken zaten `+MINUTES_PER_DAY` ile uzatılmış hâlde
    saklanır) — bu tipin DIŞINDA `preferred_end_time`'ın HAM (uzatılmamış)
    hâli hiçbir yerde kullanılmamalı.

    Bu strateji İLE `ortools_strategy.py` bu TEK yoldan (`parse`) türetilen
    `start_minutes`/`end_minutes` çiftini kullanır — iki stratejinin aynı
    girdiyi FARKLI yorumlaması yapısal olarak imkânsız hâle gelir (bkz.
    modül docstring "Overnight Time Ranges")."""
    start_minutes: int
    end_minutes: int
    is_overnight: bool

    @property
    def duration_minutes(self) -> int:
        return self.end_minutes - self.start_minutes

    @classmethod
    def parse(cls, start_raw: str, end_raw: str) -> "PlanningTimeWindow":
        """'HH:MM','HH:MM' → `PlanningTimeWindow`. `start == end` HÂLÂ
        geçersiz (mevcut sözleşme korunuyor — bkz. modül docstring) ve
        `ValueError` fırlatır; ayrıştırma başarısız olursa `_parse_hhmm`'in
        kendi `ValueError`'ı zaten yayılır. Her iki durumda da çağıran
        taraf (her iki strateji de) bunu yakalayıp `FALLBACK_START`/
        `FALLBACK_END`'e düşer — DEĞİŞMEDİ, yalnızca "ne zaman fallback"
        koşulu `end <= start` yerine `end == start` oldu."""
        start_m = _parse_hhmm(start_raw)
        end_m = _parse_hhmm(end_raw)
        if end_m == start_m:
            raise ValueError("preferred_start_time ve preferred_end_time eşit olamaz")
        is_overnight = end_m < start_m
        extended_end = end_m + MINUTES_PER_DAY if is_overnight else end_m
        return cls(start_minutes=start_m, end_minutes=extended_end, is_overnight=is_overnight)


def _day_budget(day_start: int, day_end: int) -> int:
    """Bir planlama gününün toplam dakika bütçesi — `day_end` HAM (henüz
    uzatılmamış) ya da zaten SÜREKLİ (uzatılmış) olabilir, ikisi için de
    aynı doğru sonucu verir (idempotent): `day_end < day_start` ise
    overnight kabul edilip `+MINUTES_PER_DAY` ile uzatılır, aksi halde
    değişmeden kullanılır."""
    ext_end = day_end + MINUTES_PER_DAY if day_end < day_start else day_end
    return ext_end - day_start


def _day_relative_window(open_m: int, close_m: int, day_start: int) -> Tuple[int, int]:
    """Bir mekanın HAM (open_m, close_m) günlük penceresini, VERİLEN
    `day_start`'a göre gün-göreli, SÜREKLİ bir (rel_open, rel_close)
    çiftine çevirir — `rel_close >= rel_open` HER ZAMAN garantidir (üç
    dalın hiçbiri bunu bozamaz, bkz. aşağıdaki yorumlar), ama pencere bu
    planlama gününü hiç örtmüyorsa (bkz. `_window_overlaps_day`) sonuç
    `[0, day_budget]` dışına taşabilir — çağıran taraf ÖNCE örtüşmeyi
    kontrol etmeli.

    Üç durum (ilk eşleşen kazanır):
      1. Mekan `day_start` başladığında ZATEN açık (bugünün — day_start'tan
         ÖNCE başlamış — penceresi hâlâ sürüyor): `rel_open = 0` (mevcut,
         bu milestone'dan ÖNCEki `max(0, open_m - day_start)` davranışıyla
         BİREBİR aynı sonuç).
      2. Mekan `day_start`'tan SONRA, bugün açılıyor: `rel_open = open_m -
         day_start` (yine mevcut davranışla aynı).
      3. Bugünün penceresi `day_start`'tan ÖNCE zaten KAPANDI — ilgili olan
         YARININ (ertesi takvim gününün) penceresi: `+MINUTES_PER_DAY` ile
         ileri sarılır. Bu dal, `day_start` GEÇ bir saatteyken (ör. bir
         overnight planlama penceresinin kendisi) `open_m` KÜÇÜK bir sayı
         olan (ör. "00:00-04:00") mekanların doğru yorumlanması için
         GEREKLİ — aksi halde 1. dal yanlışlıkla "zaten açık" derdi (bkz.
         docs/trip-optimizer.md "Overnight Time Ranges → Case C").
    """
    ext_close_today = close_m + MINUTES_PER_DAY if close_m < open_m else close_m
    if open_m <= day_start < ext_close_today:
        return 0, ext_close_today - day_start
    if open_m >= day_start:
        return open_m - day_start, ext_close_today - day_start
    return open_m + MINUTES_PER_DAY - day_start, ext_close_today + MINUTES_PER_DAY - day_start


def _window_overlaps_day(open_m: int, close_m: int, day_start: int, day_end: int) -> bool:
    """Bir mekanın günlük penceresi `[day_start, day_end]` planlama
    günüyle HİÇ örtüşmüyorsa `False` — bu HANGİ güne konursa konsun asla
    karşılanamaz, çünkü her gün AYNI `day_start`/`day_end`'i paylaşır
    (açılış saatleri günlük-yalnız — bkz. docs "Assumptions"). `ortools_strategy.py`
    hem `unconstrained_ids` hesaplarken (hard-constraint yolu) hem
    `_resolve_arrival` (soft/yumuşak yol, aşağıda) İÇİNDEN kullanır — TEK
    bir örtüşme tanımı, iki strateji arasında asla ayrışmaz."""
    rel_open, rel_close = _day_relative_window(open_m, close_m, day_start)
    return rel_open <= _day_budget(day_start, day_end) and rel_close >= 0


def _resolve_arrival(
    current_time: int, day_start: int, day_end: int, open_m: int, close_m: int
) -> Tuple[int, bool]:
    """Bir mekanın günlük açılış penceresine göre GERÇEK varış zamanını
    çözer — mevcut "yumuşak"/greedy zamanlama sözleşmesi (Req 3'ün
    "arrival before opening is clipped silently"/"arrival after closing
    gets a conflict warning" ikilisi), artık overnight-doğru, ama AKSİ
    HALDE tamamen DEĞİŞMEDEN:

      - Mekanın kendi (open_m, close_m) penceresi overnight'sa (`close_m <
        open_m`) `close_m` SÜREKLİ hâle `+MINUTES_PER_DAY` ile uzatılır —
        bkz. modül docstring "Overnight Time Ranges". Aksi halde (aynı-gün
        pencere) hiçbir şey değişmez.
      - `current_time` ZATEN bu (uzatılmış) pencereyi geçmişse VE
        pencerenin BİR SONRAKİ (ertesi takvim günü) tekrarı hâlâ bu
        planlama gününün bütçesi (`day_end`) İÇİNDE kalıyorsa — o
        sonraki tekrara geçilir (bkz. docs "Overnight Time Ranges → Case
        C": `preferred_end_time` gece yarısını aşan bir planlama günü
        için, `"00:00-04:00"` gibi ERKEN bir mekan penceresi, o akşamın
        "ertesi gün sabahı" kısmına aittir, dünün geçmiş bir penceresine
        DEĞİL). Bu kaydırma yalnızca GENUINELY bu güne sığdığında
        uygulanır — sığmıyorsa (Case D: aynı-gün bir planlama penceresi,
        overnight bir mekan penceresi karşısında) hiçbir kaydırma
        yapılmaz, aşağıdaki mevcut "kapanıştan sonra ise uyarı ver, DUR"
        dalı devreye girer — bu da mevcut flush/taşma mekanizmasının
        (bkz. `optimize()`) bu mekanı doğal olarak bir sonraki güne
        itmesini sağlar, YAPAY bir "asla erişilemez" kısayolu OLMADAN.
      - `current_time` açılıştan ÖNCEyse açılışa kadar SESSİZCE bekler
        (mevcut davranış); bekledikten SONRA bile pencere kapanmışsa
        (yalnızca dejenere pencereler için mümkün) ya da `current_time`
        zaten kapanıştan sonraysa (ve yukarıdaki kaydırma uygulanamadıysa)
        çakışma bayrağı `True` döner — DUR, yeniden zamanlamaz (mevcut "v1
        duraklar arasında yeniden dağıtım yapmaz" sözleşmesiyle birebir
        aynı).

    Döner: (nihai varış zamanı, çakışma-uyarısı-gerekiyor-mu).
    """
    ext_close = close_m + MINUTES_PER_DAY if close_m < open_m else close_m
    if current_time >= ext_close and open_m + MINUTES_PER_DAY <= day_end:
        open_m += MINUTES_PER_DAY
        ext_close += MINUTES_PER_DAY

    arrival = current_time
    if arrival < open_m:
        arrival = open_m  # açılışı bekle — sessizce, bu doğru davranış
    conflict = arrival >= ext_close
    return arrival, conflict


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    lat1_r, lng1_r, lat2_r, lng2_r = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def _date_for(start_date: Optional[str], day_index: int) -> Optional[str]:
    if not start_date:
        return None
    try:
        base = date.fromisoformat(start_date)
        return (base + timedelta(days=day_index)).isoformat()
    except ValueError:
        return None


class GreedyDistanceStrategy(RouteOptimizationStrategy):

    @property
    def name(self) -> str:
        return "greedy_distance"

    def _nearest_neighbor_order(self, places: List[PlaceInput]) -> List[PlaceInput]:
        n = len(places)
        if n <= 1:
            return list(places)

        visited = [False] * n
        order = [0]
        visited[0] = True
        current = 0
        for _ in range(n - 1):
            best_idx, best_dist = None, float("inf")
            for j in range(n):
                if visited[j]:
                    continue
                d = haversine_km(places[current].lat, places[current].lng, places[j].lat, places[j].lng)
                if d < best_dist:
                    best_idx, best_dist = j, d
            visited[best_idx] = True
            order.append(best_idx)
            current = best_idx
        return [places[i] for i in order]

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
            window = PlanningTimeWindow.parse(constraints.preferred_start_time, constraints.preferred_end_time)
        except (ValueError, AttributeError):
            window = PlanningTimeWindow.parse(FALLBACK_START, FALLBACK_END)
        # `day_end` bu noktadan itibaren HER ZAMAN SÜREKLİ (overnight ise
        # +MINUTES_PER_DAY ile uzatılmış) — aşağıdaki `departure > day_end`
        # gibi TÜM karşılaştırmalar bu yüzden overnight-doğru (bkz.
        # "Overnight Time Ranges").
        day_start, day_end = window.start_minutes, window.end_minutes

        max_days = constraints.duration_days if (constraints.duration_days and constraints.duration_days >= 1) else None

        ordered = self._nearest_neighbor_order(places)
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
                arrival, conflict = _resolve_arrival(arrival, day_start, day_end, open_m, close_m)
                if conflict:
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
