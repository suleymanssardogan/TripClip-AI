import XCTest
@testable import TripClipApp

/// `PlanningDate` — Trip Planning Date milestone'unun tip-güvenli dahili
/// gösterimi. Tamamen saf/senkron, SwiftUI/ağ'a bağımlı değil (bkz.
/// docs/ios-trip-optimizer.md "Trip Planning Date").
final class PlanningDateTests: XCTestCase {

    // MARK: - apiValue (ağ sınırındaki tek dönüşüm noktası)

    func test_apiValue_zeroPadsSingleDigitMonthAndDay() {
        XCTAssertEqual(PlanningDate(year: 2026, month: 9, day: 1).apiValue, "2026-09-01")
        XCTAssertEqual(PlanningDate(year: 2026, month: 1, day: 5).apiValue, "2026-01-05")
    }

    func test_apiValue_doesNotPadDoubleDigitValues() {
        XCTAssertEqual(PlanningDate(year: 2026, month: 12, day: 25).apiValue, "2026-12-25")
    }

    // MARK: - Date köprüsü (DatePicker binding'i) — multi-day derivation'ın temeli

    func test_dateRoundTrip_preservesYearMonthDay() {
        let original = PlanningDate(year: 2026, month: 8, day: 12)
        let roundTripped = PlanningDate(date: original.asDate)

        XCTAssertEqual(roundTripped, original)
    }

    /// Takvim günü aritmetiği (backend'in `_date_for`'u zaten yapıyor, bkz.
    /// docs/trip-optimizer.md) 24 saat eklemek DEĞİL, `Calendar`'ın kendi
    /// gün ekleme mekanizmasıdır — bu test, `asDate`'in üzerine `Calendar`
    /// ile bir gün eklemenin doğru bir sonraki takvim gününü ürettiğini
    /// (ay/yıl sınırları dahil) doğrular, `PlanningDate`'in `Date`
    /// köprüsünün bu tür aritmetiği bozmadığını kanıtlar.
    func test_addingOneCalendarDay_viaDateBridge_crossesMonthBoundaryCorrectly() {
        let lastDayOfMonth = PlanningDate(year: 2026, month: 1, day: 31)
        let nextDay = Calendar.current.date(byAdding: .day, value: 1, to: lastDayOfMonth.asDate)!

        XCTAssertEqual(PlanningDate(date: nextDay), PlanningDate(year: 2026, month: 2, day: 1))
    }

    func test_addingOneCalendarDay_crossesYearBoundaryCorrectly() {
        let lastDayOfYear = PlanningDate(year: 2026, month: 12, day: 31)
        let nextDay = Calendar.current.date(byAdding: .day, value: 1, to: lastDayOfYear.asDate)!

        XCTAssertEqual(PlanningDate(date: nextDay), PlanningDate(year: 2027, month: 1, day: 1))
    }

    // MARK: - displayString (tr_TR, APIDate'in kendi biçimi)

    func test_displayString_matchesTurkishFormat() {
        XCTAssertEqual(PlanningDate(year: 2026, month: 8, day: 12).displayString, "12 Ağustos 2026")
    }

    func test_displayString_januaryIsOcak() {
        XCTAssertEqual(PlanningDate(year: 2026, month: 1, day: 1).displayString, "1 Ocak 2026")
    }

    // MARK: - Equatable sanity

    func test_equality_sameYearMonthDay_areEqual() {
        XCTAssertEqual(
            PlanningDate(year: 2026, month: 8, day: 12),
            PlanningDate(year: 2026, month: 8, day: 12)
        )
    }

    func test_equality_differentDay_areNotEqual() {
        XCTAssertNotEqual(
            PlanningDate(year: 2026, month: 8, day: 12),
            PlanningDate(year: 2026, month: 8, day: 13)
        )
    }
}
