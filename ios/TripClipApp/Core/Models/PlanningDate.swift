import Foundation

/// Bir itinerary'nin (opsiyonel) planlama tarihi — takvim günü, saat dilimi
/// YOK. `ClockTime` ile AYNI tasarım dili (bkz. o dosyanın doc yorumu):
/// bilerek `Date` DEĞİL — backend'in kendi `start_date`/`ItineraryDayResponse.date`
/// alanları da saf takvim tarihleridir (saat dilimsiz `"YYYY-MM-DD"`,
/// Python'ın `date.isoformat()`'ı), `Date` kullanmak alakasız saat dilimi/saat
/// karmaşıklığı taşırdı. Sistemde HİÇBİR YERDE saat dilimi kavramı yok (bkz.
/// docs/trip-optimizer.md "Assumptions") — bu tür de onu icat etmiyor, bkz.
/// docs/ios-trip-optimizer.md "Trip Planning Date".
struct PlanningDate: Equatable {
    var year:  Int
    var month: Int
    var day:   Int

    /// Backend'in `"YYYY-MM-DD"` biçimi — `OptimizeTripRequest.start_date`
    /// ile birebir aynı (`date.isoformat()`).
    var apiValue: String { String(format: "%04d-%02d-%02d", year, month, day) }
}

// MARK: - SwiftUI DatePicker köprüsü

extension PlanningDate {
    /// `DatePicker(selection:displayedComponents: .date)` yalnızca `Date` ile
    /// çalışır — SwiftUI'nin saat dilimsiz bir takvim-günü tipi yok. Saat/
    /// dakika/saniye bileşenleri önemsiz (yalnızca yıl/ay/gün okunuyor/
    /// yazılıyor, bkz. `init(date:)`).
    var asDate: Date {
        Calendar.current.date(from: DateComponents(year: year, month: month, day: day)) ?? Date()
    }

    init(date: Date) {
        let components = Calendar.current.dateComponents([.year, .month, .day], from: date)
        self.year  = components.year ?? 1970
        self.month = components.month ?? 1
        self.day   = components.day ?? 1
    }

    /// "12 Ağustos 2026" — `APIDate`'in kendi tr_TR gösterim biçimiyle aynı
    /// (bkz. `Itinerary.formattedCreatedAt`) — burada yeni bir biçim icat
    /// edilmiyor.
    var displayString: String { APIDate.displayString(from: asDate) }
}
