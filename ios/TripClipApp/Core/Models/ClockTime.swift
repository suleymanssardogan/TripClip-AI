import Foundation

/// Saat-dakika çifti (tarihsiz, saat dilimsiz) — AI Trip Optimizer'ın
/// `preferred_start_time`/`preferred_end_time` alanları için tip-güvenli
/// dahili gösterim. Bilerek `Date` DEĞİL: bir "gün içi saat" bir tarihe/saat
/// dilimine sahip değildir, `Date` kullanmak DST/gün sınırı gibi
/// alakasız karmaşıklıklar taşırdı. Ekran boyunca (`TripOptimizerConfigViewModel`,
/// `TripOptimizerViewModel`) bu tür taşınır; yalnızca ağ sınırında
/// (`Endpoint.body`) `apiValue` ile backend'in beklediği `"HH:MM"`
/// dizgisine çevrilir (bkz. docs/ios-trip-optimizer.md "Preferred Start/End
/// Time Controls").
struct ClockTime: Equatable, Comparable {
    var hour:   Int
    var minute: Int

    static func < (lhs: ClockTime, rhs: ClockTime) -> Bool {
        (lhs.hour, lhs.minute) < (rhs.hour, rhs.minute)
    }

    /// Backend'in `"HH:MM"` biçimi — core-api/mobile-bff `OptimizeTripRequest.preferred_start_time`/
    /// `preferred_end_time` ile birebir aynı (bkz. `optimization_dto.py`).
    var apiValue: String { String(format: "%02d:%02d", hour, minute) }
}

extension ClockTime {
    /// core-api'nin kendi varsayılanlarıyla BİREBİR aynı (bkz.
    /// `OptimizeTripRequest.preferred_start_time`/`preferred_end_time`
    /// default'ları, `"09:00"`/`"18:00"`) — Req 3: "the iOS UI should
    /// reflect those values", uydurulmuş bir varsayılan değil.
    static let defaultStart = ClockTime(hour: 9, minute: 0)
    static let defaultEnd   = ClockTime(hour: 18, minute: 0)
}

// MARK: - SwiftUI DatePicker köprüsü

extension ClockTime {
    /// `DatePicker(selection:displayedComponents: .hourAndMinute)` yalnızca
    /// `Date` ile çalışır — SwiftUI'nin saat-yalnız bir seçici için native bir
    /// tipi yok. Hangi takvim günü kullanıldığı önemsiz (yalnızca saat/dakika
    /// bileşenleri okunuyor/yazılıyor); `Date()` (bugün) sabit referans olarak
    /// kullanılıyor.
    var asDate: Date {
        Calendar.current.date(bySettingHour: hour, minute: minute, second: 0, of: Date()) ?? Date()
    }

    init(date: Date) {
        let components = Calendar.current.dateComponents([.hour, .minute], from: date)
        self.hour   = components.hour ?? 0
        self.minute = components.minute ?? 0
    }
}
