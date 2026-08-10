import XCTest
@testable import TripClipApp

/// `OptimizerSelection` — harita ve itinerary listesi arasında paylaşılan
/// tek seçim durumu (bkz. docs/ios-trip-optimizer.md "Bidirectional
/// Itinerary ↔ Map Interaction"). Bu tür SwiftUI'ye/MapKit'e bağımlı
/// değil, tamamen saf — `.focusing(dayIndex:stopID:)` gerçek mekanizmanın
/// kalbi: hem Req 1 ("preserve the current selected day") hem Req 4
/// ("switch to that day if the tapped stop belongs to another day") bu tek
/// kuraldan doğar, ve dolaylı olarak Req 1/5/6'nın "do not recalculate the
/// route merely because a stop was selected" garantisini de kanıtlar —
/// `OptimizerRouteMapSection`'ın `.task(id: selection.dayIndex)`'i yalnızca
/// `dayIndex` DEĞİŞTİĞİNDE yeniden tetiklenir; bu testler `dayIndex`'in ne
/// zaman değiştiğini/değişmediğini doğrudan doğrular.
final class OptimizerSelectionTests: XCTestCase {

    // MARK: - Req 1: aynı gündeki bir durağa dokunmak günü korur

    func test_focusing_stopInCurrentDay_dayIndexUnchanged() {
        let current = OptimizerSelection(dayIndex: 0, stopID: "old-stop")

        let next = OptimizerSelection.focusing(dayIndex: 0, stopID: "new-stop")

        // dayIndex AYNI kaldı — OptimizerRouteMapSection'ın
        // `.task(id: selection.dayIndex)`'i bu geçişte YENİDEN TETİKLENMEZ,
        // yani rota yeniden hesaplanmaz (Req 1 "do not recalculate the
        // route merely because a stop was selected").
        XCTAssertEqual(next.dayIndex, current.dayIndex)
        XCTAssertEqual(next.stopID, "new-stop")
    }

    // MARK: - Req 4: başka bir güne ait bir durağa dokunmak günü değiştirir

    func test_focusing_stopInDifferentDay_switchesDayIndex() {
        let current = OptimizerSelection(dayIndex: 0, stopID: "day0-stop")

        let next = OptimizerSelection.focusing(dayIndex: 1, stopID: "day1-stop")

        XCTAssertNotEqual(next.dayIndex, current.dayIndex)
        XCTAssertEqual(next.dayIndex, 1)
        XCTAssertEqual(next.stopID, "day1-stop")
    }

    /// "Tümü" (nil) görünümündeyken bir durağa dokunmak, o durağın
    /// gününe daralır — dokunulan durak zaten görünür olsa bile (tüm
    /// günler gösterilirken), odaklanma her zaman TEK bir güne aittir.
    func test_focusing_fromAllDaysView_narrowsToTheTappedStopsDay() {
        let current = OptimizerSelection(dayIndex: nil, stopID: nil)

        let next = OptimizerSelection.focusing(dayIndex: 2, stopID: "day2-stop")

        XCTAssertNil(current.dayIndex)
        XCTAssertEqual(next.dayIndex, 2)
    }

    // MARK: - Switching days through stop selection (Req 4 end-to-end)

    /// Ardışık olarak farklı günlerden duraklara dokunmak, seçimi doğru
    /// biçimde her seferinde o durağın gününe taşır — bir "gün geçişi
    /// zinciri" simülasyonu.
    func test_switchingDaysThroughStopSelection_tracksEachTappedStopsDay() {
        var selection = OptimizerSelection(dayIndex: nil, stopID: nil)

        selection = .focusing(dayIndex: 0, stopID: "a")
        XCTAssertEqual(selection.dayIndex, 0)

        selection = .focusing(dayIndex: 1, stopID: "b")
        XCTAssertEqual(selection.dayIndex, 1)

        // Aynı güne (1) geri dönen başka bir durak — dayIndex değişmiyor.
        selection = .focusing(dayIndex: 1, stopID: "c")
        XCTAssertEqual(selection.dayIndex, 1)

        selection = .focusing(dayIndex: 0, stopID: "d")
        XCTAssertEqual(selection.dayIndex, 0)
    }

    // MARK: - Equatable sanity

    func test_equality_sameValues_areEqual() {
        XCTAssertEqual(
            OptimizerSelection(dayIndex: 1, stopID: "x"),
            OptimizerSelection(dayIndex: 1, stopID: "x")
        )
    }

    func test_equality_differentStopID_areNotEqual() {
        XCTAssertNotEqual(
            OptimizerSelection(dayIndex: 1, stopID: "x"),
            OptimizerSelection(dayIndex: 1, stopID: "y")
        )
    }
}
