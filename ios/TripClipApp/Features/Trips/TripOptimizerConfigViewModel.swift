import Foundation

/// AI Trip Optimizer'ı çalıştırmadan ÖNCE gösterilen yapılandırma ekranının
/// durumu — hangi mekanların optimize edileceği ve kaç güne yayılacağı.
/// Bilerek AĞ ÇAĞRISI YAPMAZ: seçim yalnızca optimizer isteğinin girdisidir,
/// `TripStop`'u hiçbir şekilde mutasyona uğratmaz (bkz. spesifikasyonun
/// "Selection is only optimizer input" gereksinimi) — gerçek istek yalnızca
/// "Optimize Et" ile `TripOptimizerViewModel.optimize` çağrıldığında gider.
///
/// Persistent Optimizer Configuration milestone'undan itibaren: bu tipin
/// TÜM durumu (`OptimizerConfiguration` biçiminde) `OptimizerConfigurationStore`'a
/// (ekran ömrünü aşan, uygulama oturumu boyunca yaşayan, trip-bazlı paylaşılan
/// önbellek — bkz. o tipin kendi doc yorumu) `init`'te GERİ YÜKLENİR ve her
/// mutasyondan sonra GERİ YAZILIR — bkz. `persistConfiguration()`. Ekran her
/// yeniden açıldığında sıfırdan başlamak yerine, AYNI trip için son
/// bırakılan yapılandırma geri gelir.
@Observable
@MainActor
final class TripOptimizerConfigViewModel {

    /// Backend'in kendi alt sınırı (`duration_days >= 1`, bkz.
    /// OptimizationService) dışında bir üst sınır uygulamıyor — bu yalnızca
    /// makul bir UI üst sınırı, sunucu tarafında ayrıca doğrulanmıyor/
    /// gerektirmiyor (bkz. docs/ios-trip-optimizer.md "Duration").
    static let durationRange = 1...30

    let stops: [TripStop]
    /// `OptimizerConfigurationStore`'un dictionary anahtarı — `Trip.id`
    /// (bkz. `TripDetailView`'ın `trip.id`'yi geçirdiği çağrı yeri).
    private let tripID: Int
    private let configStore: OptimizerConfigurationStore

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

    /// Haritanın (`OptimizerRouteMapSection`) rota gösterim tercihiyle
    /// PAYLAŞILAN, tek gerçek kaynak — `OptimizerConfigurationStore` her
    /// ikisinin de okuduğu/yazdığı ORTAK depodur (bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Transport Mode
    /// Sync"). Optimizer Configuration Transport Mode Picker milestone'undan
    /// itibaren bu ekranın KENDİ UI'ı da var (`TripOptimizerConfigView.transportModeSection`)
    /// — kullanıcı burada değiştirebildiği gibi, haritada da değiştirebilir;
    /// hangi taraftan değişirse değişsin AYNI `OptimizerConfigurationStore`
    /// kaydına yazılır, ikinci bir state modeli YOK.
    private(set) var transportMode: OptimizerTransportMode = .automobile

    /// `stops` sırası Trip'in kendi kanonik durak sırasıdır. `tripID`/
    /// `configStore` varsayılanlı — bu dosyanın kendi testlerinin
    /// ÇOĞUNLUĞU (yapılandırma kalıcılığıyla hiç ilgilenmeyen, salt
    /// seçim/süre/saat mekaniğini test eden testler) `stops:` dışında hiçbir
    /// şey belirtmeden derlenmeye devam eder — `OptimizerRouteCalculator`'ın
    /// kendi `cache:` parametresiyle AYNI geriye-dönük-uyumluluk deseni
    /// (bkz. docs/ios-trip-optimizer.md "Persistent Optimizer Route Cache").
    ///
    /// Geri yükleme SENKRON olarak, tam burada gerçekleşir (Req 8 "must
    /// happen before the first meaningful UI render") — bu tip zaten hiç ağ
    /// çağrısı yapmıyor, bu yüzden `OptimizerSelectionStore`'un
    /// `TripOptimizerView.load()` içindeki async-sonrası deseninin aksine,
    /// burada geciktirilecek bir "itinerary yüklensin" adımı hiç yok;
    /// kaydedilmiş yapılandırma varsa geçerli `stops` listesine göre
    /// DOĞRULANIR/UZLAŞTIRILIR (bkz. `Self.reconciled`) ve doğrudan
    /// başlangıç durumu olarak kullanılır — kullanıcı asla bir "varsayılan"
    /// anlık görüntüsü görüp hemen ardından değiştiğini GÖRMEZ.
    init(
        tripID: Int = 0, stops: [TripStop],
        configStore: OptimizerConfigurationStore = OptimizerConfigurationStore()
    ) {
        self.tripID = tripID
        self.stops = stops
        self.configStore = configStore

        let availablePlaceIDs = Set(stops.map(\.placeId))
        let resolved = Self.reconciled(
            saved: configStore.configuration(for: tripID), availablePlaceIDs: availablePlaceIDs
        )
        self.selectedPlaceIDs   = resolved.selectedPlaceIDs
        self.durationDays       = resolved.durationDays
        self.preferredStartTime = resolved.preferredStartTime
        self.preferredEndTime   = resolved.preferredEndTime
        self.preferredStartDate = resolved.startDate
        self.transportMode      = resolved.transportMode

        persistConfiguration()
    }

    /// Kaydedilmiş bir yapılandırmayı (varsa) GEÇERLİ `stops`'a göre
    /// doğrulanmış/uzlaştırılmış bir `OptimizerConfiguration`'a çevirir —
    /// hiçbir zaman KÖRÜ KÖRÜNE geri yüklenmez (Req 9, CRİTİK). Kayıt yoksa
    /// (ilk açılış) BUGÜNKÜ (bu milestone ÖNCESİ) varsayılan davranışın
    /// AYNISINI üretir (Req 15).
    private static func reconciled(
        saved: OptimizerConfiguration?, availablePlaceIDs: Set<Int>
    ) -> OptimizerConfiguration {
        guard let saved else {
            return .defaults(selectedPlaceIDs: availablePlaceIDs)
        }

        // Seçili mekanlar: kaydedilmiş seçimle GEÇERLİ mekanların kesişimi
        // — artık var olmayan ID'ler düşer, kullanıcının önceki AÇIK
        // deselection'ları korunur, YENİ (daha önce hiç görülmemiş)
        // mekanlar OTOMATİK seçilmez (spesifikasyonun kendi örneği:
        // saved [1,2,3,4], current [1,2,4,5] → restore [1,2,4] — 5 YOK).
        let reconciledSelection = saved.selectedPlaceIDs.intersection(availablePlaceIDs)

        // Süre: mevcut aralığın dışına taşmışsa (pratikte olmaz, VM zaten
        // hep aralık içinde tutar — savunma amaçlı) sınırların içine kırp;
        // `nil` (Otomatik) her zaman geçerli.
        let reconciledDuration = saved.durationDays.map {
            min(max($0, durationRange.lowerBound), durationRange.upperBound)
        }

        // Zaman aralığı: TEK geçersizlik kuralı `start == end` (bkz.
        // `isTimeRangeValid` — overnight aralıklar dahil HER ŞEY geçerli,
        // `end < start` YENİDEN reddedilmiyor). Geçersizse mevcut
        // varsayılanlara düş.
        let (reconciledStart, reconciledEnd): (ClockTime, ClockTime) =
            saved.preferredStartTime != saved.preferredEndTime
                ? (saved.preferredStartTime, saved.preferredEndTime)
                : (.defaultStart, .defaultEnd)

        return OptimizerConfiguration(
            selectedPlaceIDs: reconciledSelection, durationDays: reconciledDuration,
            preferredStartTime: reconciledStart, preferredEndTime: reconciledEnd,
            // Tarih: hiçbir doğrulama kuralı yok (bkz. `PlanningDate`'in
            // kendisi de hiç doğrulama yapmıyor) — olduğu gibi geri yüklenir.
            startDate: saved.startDate,
            // Taşıma modu: yalnızca iki geçerli değer var, ikisi de her
            // zaman geçerli — olduğu gibi geri yüklenir.
            transportMode: saved.transportMode
        )
    }

    /// TEK merkezi kalıcılık noktası — her mutasyon (aşağıdaki
    /// setter/toggle/select/deselect/increment/decrement) tam olarak bunu
    /// çağırır; yapılandırma inşa etme/kaydetme MANTIĞI burada tek bir
    /// yerde yaşıyor (spesifikasyonun "prefer one centralized save
    /// mechanism rather than scattering store.save(...) through every
    /// setter" gereksinimi — her mutasyon bu TEK fonksiyonu çağırır, kendi
    /// kaydetme mantığını TEKRARLAMAZ).
    private func persistConfiguration() {
        configStore.save(
            OptimizerConfiguration(
                selectedPlaceIDs: selectedPlaceIDs, durationDays: durationDays,
                preferredStartTime: preferredStartTime, preferredEndTime: preferredEndTime,
                startDate: preferredStartDate, transportMode: transportMode
            ),
            for: tripID
        )
    }

    var selectedCount: Int { selectedPlaceIDs.count }

    /// Backend'in kendi kuralıyla BİREBİR aynı (bkz. `OptimizationService`
    /// — Overnight Time Ranges milestone'undan itibaren yalnızca EŞİT
    /// değerler reddedilir, `end < start` artık GEÇERLİ bir overnight
    /// planlama penceresi anlamına gelir, ör. `18:00 → 01:00`). Bu katman
    /// yalnızca ÇİFTİN sözdizimsel olarak geçerli bir planlama aralığı
    /// olup olmadığını belirler — hangi mekanların bu pencereye SIĞACAĞI
    /// (açılış saatleriyle etkileşim, gün-farkında zamanlama) tamamen
    /// backend'in sorumluluğu, burada TEKRARLANMAZ (bkz.
    /// docs/trip-optimizer.md "Overnight Time Ranges"). İstemci bunu
    /// önceden engelleyerek kullanıcıya sunucuya gitmeden anında geri
    /// bildirim verir; sunucu doğrulaması yine de otoriter kalır.
    var isTimeRangeValid: Bool { preferredStartTime != preferredEndTime }

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
        persistConfiguration()
    }

    /// Yalnızca bitiş saatini değiştirir — başlangıç saatine ASLA
    /// dokunmaz ("changing only the end time doesn't modify the start
    /// time").
    func setPreferredEndTime(_ time: ClockTime) {
        preferredEndTime = time
        persistConfiguration()
    }

    /// Opsiyonel planlama tarihi — core-api'nin kendi `start_date`
    /// alanıyla AYNI "Otomatik" deseni (`durationDays` gibi): `nil` =
    /// "belirli bir tarih yok", günler yalnızca sıra numarasıyla
    /// gösterilir. Backend'de bunun için bir varsayılan YOK (09:00/18:00
    /// gibi) — bu yüzden `preferredStartTime`/`preferredEndTime`'ın
    /// aksine somut bir varsayılan değer yerine `nil` ile başlar (bkz.
    /// docs/ios-trip-optimizer.md "Trip Planning Date").
    private(set) var preferredStartDate: PlanningDate? = nil

    /// Planlama tarihini ayarlar/temizler — `nil` geçmek "Otomatik"a
    /// döner. Yalnızca bu alanı değiştirir; seçim/süre/saat state'lerine
    /// dokunmaz.
    func setPreferredStartDate(_ date: PlanningDate?) {
        preferredStartDate = date
        persistConfiguration()
    }

    /// Yalnızca bu alanı ayarlar — diğer alanlara (yer seçimi/süre/saat/
    /// tarih) hiç dokunmaz. `TripOptimizerConfigView.transportModeSection`
    /// tarafından çağrılır; haritanın kendi seçicisiyle AYNI
    /// `OptimizerConfigurationStore` kaydını günceller (bkz. `transportMode`
    /// property'sinin kendi doc yorumu).
    func setTransportMode(_ mode: OptimizerTransportMode) {
        transportMode = mode
        persistConfiguration()
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
        persistConfiguration()
    }

    func selectAll() {
        selectedPlaceIDs = Set(stops.map(\.placeId))
        persistConfiguration()
    }

    func deselectAll() {
        selectedPlaceIDs.removeAll()
        persistConfiguration()
    }

    /// Otomatik (nil) → 1 → 2 → … → `durationRange.upperBound` (üst sınırda
    /// no-op — spesifikasyonun "duration larger than supported bounds"
    /// senaryosu: UI değeri asla sınırın dışına çıkaramaz).
    func incrementDuration() {
        let next = (durationDays ?? 0) + 1
        durationDays = min(next, Self.durationRange.upperBound)
        persistConfiguration()
    }

    /// `durationRange.lowerBound` → … → 1 → Otomatik (nil) → no-op (zaten
    /// Otomatik'te daha aşağı inilemez — "duration smaller than supported
    /// bounds" senaryosu: UI hiçbir zaman 0 veya negatif bir değer üretemez).
    func decrementDuration() {
        guard let current = durationDays else { return }
        durationDays = current > Self.durationRange.lowerBound ? current - 1 : nil
        persistConfiguration()
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
