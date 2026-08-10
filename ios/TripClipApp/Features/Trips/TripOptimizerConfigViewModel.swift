import Foundation

/// AI Trip Optimizer'ı çalıştırmadan ÖNCE gösterilen yapılandırma ekranının
/// durumu — hangi mekanların optimize edileceği ve kaç güne yayılacağı.
/// Bilerek AĞ ÇAĞRISI YAPMAZ: seçim yalnızca optimizer isteğinin girdisidir,
/// `TripStop`'u hiçbir şekilde mutasyona uğratmaz (bkz. spesifikasyonun
/// "Selection is only optimizer input" gereksinimi) — gerçek istek yalnızca
/// "Optimize Et" ile `TripOptimizerViewModel.optimize` çağrıldığında gider.
@Observable
@MainActor
final class TripOptimizerConfigViewModel {

    /// Backend'in kendi alt sınırı (`duration_days >= 1`, bkz.
    /// OptimizationService) dışında bir üst sınır uygulamıyor — bu yalnızca
    /// makul bir UI üst sınırı, sunucu tarafında ayrıca doğrulanmıyor/
    /// gerektirmiyor (bkz. docs/ios-trip-optimizer.md "Duration").
    static let durationRange = 1...30

    let stops: [TripStop]
    private(set) var selectedPlaceIDs: Set<Int>
    /// nil = Otomatik — backend kendi gerekli gün sayısını türetir (mevcut,
    /// bu milestone'dan önceki tek davranış). Değiştirilmediği sürece bu
    /// varsayılan olarak kalır (spesifikasyonun "default behavior should
    /// preserve today's behavior" gereksinimi — yalnızca seçim için değil,
    /// süre için de).
    private(set) var durationDays: Int?

    /// Optimizerin günlük planlama penceresi — core-api'nin kendi
    /// `OptimizeTripRequest.preferred_start_time`/`preferred_end_time`
    /// varsayılanlarıyla BİREBİR aynı başlar (bkz. `ClockTime.defaultStart`/
    /// `defaultEnd`, Req 3 "the iOS UI should reflect those values").
    /// Mekanların kendi açılış saatleri AYRI bir kısıttır, buradan
    /// etkilenmez/etkilemez — backend her ikisini de kendi tarafında
    /// birleştirir (bkz. docs/trip-optimizer.md "Opening hours").
    private(set) var preferredStartTime: ClockTime = .defaultStart
    private(set) var preferredEndTime:   ClockTime = .defaultEnd

    /// `stops` sırası Trip'in kendi kanonik durak sırasıdır — varsayılan
    /// seçim TÜMÜ (spesifikasyonun 1. gereksinimi: "Default behavior should
    /// preserve today's behavior: all current Trip stops selected").
    init(stops: [TripStop]) {
        self.stops = stops
        self.selectedPlaceIDs = Set(stops.map(\.placeId))
    }

    var selectedCount: Int { selectedPlaceIDs.count }

    /// Backend'in kendi kuralıyla BİREBİR aynı (bkz. `OptimizationService`
    /// `preferred_end_time <= preferred_start_time` reddi) — istemci bunu
    /// önceden engelleyerek kullanıcıya sunucuya gitmeden anında geri
    /// bildirim verir; sunucu doğrulaması yine de otoriter kalır.
    var isTimeRangeValid: Bool { preferredStartTime < preferredEndTime }

    /// Sıfır seçili mekanla YA DA geçersiz bir zaman aralığıyla optimize
    /// edilemez (spesifikasyonun 5. gereksinimi genişletildi: "zero
    /// selected places" + "invalid time range" ikisi de istemci tarafında
    /// engellenmeli).
    var canOptimize: Bool { !selectedPlaceIDs.isEmpty && isTimeRangeValid }

    /// Yalnızca başlangıç saatini değiştirir — bitiş saatine ASLA
    /// dokunmaz (spesifikasyonun kendi test gereksinimi: "changing only
    /// the start time doesn't modify the end time").
    func setPreferredStartTime(_ time: ClockTime) {
        preferredStartTime = time
    }

    /// Yalnızca bitiş saatini değiştirir — başlangıç saatine ASLA
    /// dokunmaz ("changing only the end time doesn't modify the start
    /// time").
    func setPreferredEndTime(_ time: ClockTime) {
        preferredEndTime = time
    }

    func isSelected(_ placeID: Int) -> Bool {
        selectedPlaceIDs.contains(placeID)
    }

    func toggle(_ placeID: Int) {
        if selectedPlaceIDs.contains(placeID) {
            selectedPlaceIDs.remove(placeID)
        } else {
            selectedPlaceIDs.insert(placeID)
        }
    }

    func selectAll() {
        selectedPlaceIDs = Set(stops.map(\.placeId))
    }

    func deselectAll() {
        selectedPlaceIDs.removeAll()
    }

    /// Otomatik (nil) → 1 → 2 → … → `durationRange.upperBound` (üst sınırda
    /// no-op — spesifikasyonun "duration larger than supported bounds"
    /// senaryosu: UI değeri asla sınırın dışına çıkaramaz).
    func incrementDuration() {
        let next = (durationDays ?? 0) + 1
        durationDays = min(next, Self.durationRange.upperBound)
    }

    /// `durationRange.lowerBound` → … → 1 → Otomatik (nil) → no-op (zaten
    /// Otomatik'te daha aşağı inilemez — "duration smaller than supported
    /// bounds" senaryosu: UI hiçbir zaman 0 veya negatif bir değer üretemez).
    func decrementDuration() {
        guard let current = durationDays else { return }
        durationDays = current > Self.durationRange.lowerBound ? current - 1 : nil
    }

    /// Seçili mekanların, Trip'in kendi durak sırasını koruyan listesi —
    /// `Set` sırasız olduğundan, istek gövdesinin deterministik/okunabilir
    /// olması için Trip'in mevcut sırası temel alınır (backend zaten kendi
    /// rota sıralamasını route-first ile yeniden hesaplıyor, bu yalnızca
    /// istek inşası için).
    var selectedPlaceIDsInTripOrder: [Int] {
        stops.map(\.placeId).filter(selectedPlaceIDs.contains)
    }
}
