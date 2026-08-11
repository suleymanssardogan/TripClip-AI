import XCTest
@testable import TripClipApp

/// `APIDate.parseDateOnly` — yalnızca bu milestone'da eklenen yeni yardımcı
/// test ediliyor (`parse`/`displayString` zaten mevcut, `created_at` ile
/// dolaylı olarak kapsanıyor, kapsam dışı). Bkz. docs/ios-trip-optimizer.md
/// "Trip Planning Date".
final class APIDateTests: XCTestCase {

    func test_parseDateOnly_validDate_parsesYearMonthDay() throws {
        let date = try XCTUnwrap(APIDate.parseDateOnly("2026-09-01"))
        let components = Calendar.current.dateComponents([.year, .month, .day], from: date)

        XCTAssertEqual(components.year, 2026)
        XCTAssertEqual(components.month, 9)
        XCTAssertEqual(components.day, 1)
    }

    /// `created_at`'in `T`'li tam datetime biçimi (`parse(_:)`'in kendi
    /// ayrıştırdığı) BU fonksiyon tarafından ayrıştırılamamalı — ikisi
    /// kasıtlı olarak farklı alan türleri (bkz. `APIDate.dateOnly` doc
    /// yorumu).
    func test_parseDateOnly_rejectsFullDatetimeString() {
        XCTAssertNil(APIDate.parseDateOnly("2026-08-08T10:00:00"))
    }

    func test_parseDateOnly_invalidString_returnsNil() {
        XCTAssertNil(APIDate.parseDateOnly("not-a-date"))
    }

    func test_parseDateOnly_thenDisplayString_producesTurkishFormat() throws {
        let date = try XCTUnwrap(APIDate.parseDateOnly("2026-08-12"))
        XCTAssertEqual(APIDate.displayString(from: date), "12 Ağustos 2026")
    }

    // MARK: - shortDisplayString (Date-aware Map Day Selector milestone)

    func test_shortDisplayString_omitsYear() throws {
        let date = try XCTUnwrap(APIDate.parseDateOnly("2026-08-12"))
        XCTAssertEqual(APIDate.shortDisplayString(from: date), "12 Ağustos")
        XCTAssertFalse(APIDate.shortDisplayString(from: date).contains("2026"))
    }

    /// Ay adı `Locale`'den geliyor (Foundation'ın `FormatStyle`'ı) — elle
    /// tutulan bir Türkçe ay tablosu yok, bu yüzden Ocak gibi diğer aylar
    /// da doğru yerelleştirilmeli.
    func test_shortDisplayString_januaryIsOcak() throws {
        let date = try XCTUnwrap(APIDate.parseDateOnly("2026-01-05"))
        XCTAssertEqual(APIDate.shortDisplayString(from: date), "5 Ocak")
    }

    func test_shortDisplayString_consecutiveDates_eachFormatsCorrectly() throws {
        let d1 = try XCTUnwrap(APIDate.parseDateOnly("2026-08-12"))
        let d2 = try XCTUnwrap(APIDate.parseDateOnly("2026-08-13"))
        let d3 = try XCTUnwrap(APIDate.parseDateOnly("2026-08-14"))

        XCTAssertEqual(
            [d1, d2, d3].map(APIDate.shortDisplayString),
            ["12 Ağustos", "13 Ağustos", "14 Ağustos"]
        )
    }
}
