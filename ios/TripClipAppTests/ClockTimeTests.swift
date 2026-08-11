import XCTest
@testable import TripClipApp

/// `ClockTime` — Preferred Start/End Time Controls milestone'unun tip-güvenli
/// dahili gösterimi. Tamamen saf/senkron, SwiftUI/ağ'a bağımlı değil (bkz.
/// docs/ios-trip-optimizer.md "Preferred Start/End Time Controls").
final class ClockTimeTests: XCTestCase {

    // MARK: - apiValue (ağ sınırındaki tek dönüşüm noktası)

    func test_apiValue_zeroPadsSingleDigitHourAndMinute() {
        XCTAssertEqual(ClockTime(hour: 9, minute: 0).apiValue, "09:00")
        XCTAssertEqual(ClockTime(hour: 7, minute: 5).apiValue, "07:05")
    }

    func test_apiValue_doesNotPadDoubleDigitValues() {
        XCTAssertEqual(ClockTime(hour: 18, minute: 30).apiValue, "18:30")
        XCTAssertEqual(ClockTime(hour: 23, minute: 59).apiValue, "23:59")
    }

    func test_apiValue_midnightIsZeroZero() {
        XCTAssertEqual(ClockTime(hour: 0, minute: 0).apiValue, "00:00")
    }

    // MARK: - Defaults (core-api'nin kendi varsayılanlarıyla BİREBİR aynı)

    func test_defaultStart_matchesBackendDefault() {
        XCTAssertEqual(ClockTime.defaultStart.apiValue, "09:00")
    }

    func test_defaultEnd_matchesBackendDefault() {
        XCTAssertEqual(ClockTime.defaultEnd.apiValue, "18:00")
    }

    // MARK: - Comparable (genel amaçlı sıralama — Overnight Time Ranges
    // milestone'undan itibaren istemci-taraf zaman aralığı doğrulaması
    // (`TripOptimizerConfigViewModel.isTimeRangeValid`) ARTIK bunu
    // kullanmıyor, `!=` kullanıyor — bkz. docs/ios-trip-optimizer.md
    // "Overnight Time Ranges"; bu tip yine de genel bir sıralama
    // yeteneği olarak faydalı, bu yüzden korunuyor.

    func test_comparable_earlierHourIsLess() {
        XCTAssertLessThan(ClockTime(hour: 9, minute: 0), ClockTime(hour: 10, minute: 0))
    }

    func test_comparable_sameHourEarlierMinuteIsLess() {
        XCTAssertLessThan(ClockTime(hour: 9, minute: 0), ClockTime(hour: 9, minute: 30))
    }

    func test_comparable_equalTimesAreNotLessThanEachOther() {
        let a = ClockTime(hour: 9, minute: 0)
        let b = ClockTime(hour: 9, minute: 0)
        XCTAssertFalse(a < b)
        XCTAssertFalse(b < a)
        XCTAssertEqual(a, b)
    }

    func test_comparable_defaultStartIsBeforeDefaultEnd() {
        XCTAssertLessThan(ClockTime.defaultStart, ClockTime.defaultEnd)
    }

    // MARK: - Date köprüsü (DatePicker binding'i)

    func test_dateRoundTrip_preservesHourAndMinute() {
        let original = ClockTime(hour: 14, minute: 45)
        let roundTripped = ClockTime(date: original.asDate)

        XCTAssertEqual(roundTripped.hour, 14)
        XCTAssertEqual(roundTripped.minute, 45)
        XCTAssertEqual(roundTripped, original)
    }

    func test_dateRoundTrip_midnight() {
        let original = ClockTime(hour: 0, minute: 0)
        XCTAssertEqual(ClockTime(date: original.asDate), original)
    }
}
