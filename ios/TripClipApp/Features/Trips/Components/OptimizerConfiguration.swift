import Foundation

/// `TripOptimizerConfigViewModel`'in tüm durumunun, bir trip'e göre
/// SAKLANABİLEN, EKRAN-BAĞIMSIZ anlık görüntüsü — bkz.
/// docs/ios-trip-optimizer.md "Persistent Optimizer Configuration".
/// `TripOptimizerConfigViewModel`'in kendisi (bir SwiftUI `@State`) veya
/// herhangi bir SwiftUI/`Observable` nesnesi DEĞİL — yalnızca ekranı
/// yeniden kurmaya yetecek düz değerler.
///
/// `durationDays: Int?` — `Int` DEĞİL: `TripOptimizerConfigViewModel.durationDays`
/// zaten opsiyonel ("Otomatik" = `nil`, bkz. o tipin kendi doc yorumu),
/// bu tür o semantiği aynen yansıtıyor.
struct OptimizerConfiguration: Equatable {
    var selectedPlaceIDs:    Set<Int>
    var durationDays:        Int?
    var preferredStartTime:  ClockTime
    var preferredEndTime:    ClockTime
    var startDate:           PlanningDate?
    /// Yalnızca `OptimizerRouteMapSection`'ın haritasının BAŞLANGIÇ
    /// gösterim tercihini tohumlamak için saklanır — bkz.
    /// `TripOptimizerView`'ın `initialTransportMode` kullanımı. Yapılandırma
    /// ekranının kendisinde bu alan için henüz bir UI YOK (Req: "do not
    /// redesign the UI") — yalnızca depolanıp bir sonraki ziyarette
    /// haritaya aktarılıyor.
    var transportMode:       OptimizerTransportMode

    /// İlk açılışın (kaydedilmiş bir yapılandırma HİÇ yokken) varsayılan
    /// anlık görüntüsü — `TripOptimizerConfigViewModel.reconciled(saved: nil, ...)`
    /// VE `OptimizerConfigurationStore.updateTransportMode(...)`'ın "bu trip
    /// için henüz hiçbir kayıt yok" dalı TARAFINDAN PAYLAŞILIR (bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Transport Mode
    /// Sync") — iki ayrı yerde aynı varsayılan değerlerin TEKRARLANMASINI
    /// önler.
    static func defaults(selectedPlaceIDs: Set<Int>) -> OptimizerConfiguration {
        OptimizerConfiguration(
            selectedPlaceIDs: selectedPlaceIDs, durationDays: nil,
            preferredStartTime: .defaultStart, preferredEndTime: .defaultEnd,
            startDate: nil, transportMode: .automobile
        )
    }
}
