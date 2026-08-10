import XCTest
@testable import TripClipApp

/// `OptimizerRouteMapData` — itinerary → harita sunum verisi. Tamamen saf/
/// senkron (MapKit'e bağımlı değil), bkz. docs/ios-trip-optimizer.md
/// "Map view" testability notu: harita ÇİZİMİ zor test edilebildiğinden, bu
/// dönüşüm ayrı ve MapKit'siz test edilir.
final class OptimizerRouteMapDataTests: XCTestCase {

    private func stop(
        placeId: Int? = 1, name: String = "Mekan", lat: Double? = 41.0, lng: Double? = 29.0,
        dayIndex: Int = 0, orderIndex: Int = 0
    ) -> ItineraryStop {
        ItineraryStop(
            placeId: placeId, name: name, lat: lat, lng: lng,
            dayIndex: dayIndex, orderIndex: orderIndex,
            arrivalTime: nil, departureTime: nil, visitDurationMinutes: 30,
            travelTimeToNextMinutes: nil, travelDistanceToNextKm: nil
        )
    }

    // MARK: - One-stop itinerary

    func test_oneStopItinerary_producesSingleDayWithOneStop_noPolylineNeeded() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, name: "Ayasofya", dayIndex: 0, orderIndex: 0)])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertFalse(data.isEmpty)
        XCTAssertFalse(data.hasMultipleDays)
        XCTAssertEqual(data.days.count, 1)
        XCTAssertEqual(data.days[0].stops.count, 1)
        XCTAssertEqual(data.missingCoordinateCount, 0)
    }

    // MARK: - Multiple stops (single day)

    func test_multipleStops_singleDay_preservesOrderAndCoordinates() {
        let itinerary = OptimizerFixtures.itinerary(days: [OptimizerFixtures.oneDayWithTwoStops])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days.count, 1)
        let stops = data.days[0].stops
        XCTAssertEqual(stops.map(\.name), ["Ayasofya", "Topkapı Sarayı"])
        XCTAssertEqual(stops.map(\.orderIndex), [0, 1])
        XCTAssertEqual(stops[0].latitude, 41.0086)
        XCTAssertEqual(stops[0].longitude, 28.9802)
    }

    // MARK: - Multiple days

    func test_multipleDays_keepsDaysSeparate_hasMultipleDaysTrue() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "Gün1-A", dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "Gün1-B", dayIndex: 0, orderIndex: 1),
            ]),
            ItineraryDay(dayIndex: 1, stops: [
                stop(placeId: 3, name: "Gün2-A", dayIndex: 1, orderIndex: 0),
            ]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.hasMultipleDays)
        XCTAssertEqual(data.days.count, 2)
        XCTAssertEqual(data.days[0].stops.map(\.name), ["Gün1-A", "Gün1-B"])
        XCTAssertEqual(data.days[1].stops.map(\.name), ["Gün2-A"])
        // Her günün kendi durak dizisi var — Day 1'in son durağı Day 2'nin
        // ilk durağıyla aynı diziye ASLA karışmıyor (Req 2).
        XCTAssertFalse(data.days[0].stops.map(\.name).contains("Gün2-A"))
    }

    func test_dayIndices_areNotRenumbered_evenIfFirstDayHasNoUsableCoordinates() {
        // Gün 0'ın TÜM durakları koordinatsızsa o gün haritada hiç görünmez,
        // ama kalan günün dayIndex'i "1" olarak kalmalı (0'a kaymamalı) —
        // aksi halde gün etiketleri yanlış gösterilir.
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, lat: nil, lng: nil, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, name: "Gün2", dayIndex: 1, orderIndex: 0)]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days.count, 1)
        XCTAssertEqual(data.days[0].dayIndex, 1)
    }

    // MARK: - Missing coordinates

    func test_missingCoordinates_areOmittedFromMap_butCounted_doesNotCrash() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "Koordinatlı", lat: 41.0, lng: 29.0, dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "Koordinatsız", lat: nil, lng: nil, dayIndex: 0, orderIndex: 1),
                stop(placeId: 3, name: "Koordinatlı2", lat: 41.1, lng: 29.1, dayIndex: 0, orderIndex: 2),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.missingCoordinateCount, 1)
        XCTAssertEqual(data.days[0].stops.map(\.name), ["Koordinatlı", "Koordinatlı2"])
        // orderIndex boşluk bırakarak korunuyor (0, 2) — atlanan durak yüzünden
        // yeniden numaralandırılmıyor.
        XCTAssertEqual(data.days[0].stops.map(\.orderIndex), [0, 2])
    }

    func test_allStopsMissingCoordinates_producesEmptyDays_withFullMissingCount() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, lat: nil, lng: nil, dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, lat: nil, lng: nil, dayIndex: 0, orderIndex: 1),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 2)
        XCTAssertTrue(data.allStops.isEmpty)
    }

    /// Silinmiş bir kaynak Place — placeId nil ama lat/lng de nil olabilir
    /// (bkz. ItineraryStop doc yorumu, TripItineraryStop.place_id ondelete
    /// SET NULL). Bu durumda da crash olmamalı, yalnızca atlanmalı.
    func test_deletedSourcePlace_withNilPlaceIdAndCoordinates_isOmittedGracefully() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: nil, name: "Silinmiş mekan", lat: nil, lng: nil, dayIndex: 0, orderIndex: 0),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 1)
    }

    // MARK: - Saved itinerary rendering data

    /// `OptimizerRouteMapData` yalnızca bir `Itinerary` değeri alır —
    /// `.generate` ile mi `.viewSaved` (loadItinerary) ile mi geldiğinin
    /// farkında değil. Bu test, kayıtlı bir itinerary'nin (loadItinerary'nin
    /// döndürdüğü şekil) haritaya aynı şekilde dönüştüğünü doğruluyor.
    func test_savedItineraryShape_mapsIdenticallyToFreshlyGeneratedItinerary() {
        let saved = OptimizerFixtures.itinerary(id: 9, days: [OptimizerFixtures.oneDayWithTwoStops])

        let data = OptimizerRouteMapData(itinerary: saved)

        XCTAssertFalse(data.isEmpty)
        XCTAssertEqual(data.days[0].stops.count, 2)
        XCTAssertEqual(data.missingCoordinateCount, 0)
    }

    // MARK: - Day selection

    func test_visibleDays_nilSelection_returnsAllDays() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.visibleDays(selectedDayIndex: nil).count, 2)
    }

    func test_visibleDays_specificSelection_returnsOnlyThatDay() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, name: "Gün1", dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, name: "Gün2", dayIndex: 1, orderIndex: 0)]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        let visible = data.visibleDays(selectedDayIndex: 1)

        XCTAssertEqual(visible.count, 1)
        XCTAssertEqual(visible[0].dayIndex, 1)
        XCTAssertEqual(visible[0].stops.map(\.name), ["Gün2"])
    }

    func test_visibleDays_selectionMatchingNoDay_returnsEmpty() {
        let itinerary = OptimizerFixtures.itinerary(days: [OptimizerFixtures.oneDayWithTwoStops])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.visibleDays(selectedDayIndex: 99).isEmpty)
    }

    // MARK: - Correct stop ordering across days

    func test_stopOrdering_isPreservedPerDay_independentOfOtherDays() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "A", dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "B", dayIndex: 0, orderIndex: 1),
                stop(placeId: 3, name: "C", dayIndex: 0, orderIndex: 2),
            ]),
            ItineraryDay(dayIndex: 1, stops: [
                stop(placeId: 4, name: "D", dayIndex: 1, orderIndex: 0),
                stop(placeId: 5, name: "E", dayIndex: 1, orderIndex: 1),
            ]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days[0].stops.map(\.name), ["A", "B", "C"])
        XCTAssertEqual(data.days[1].stops.map(\.name), ["D", "E"])
    }

    // MARK: - Empty itinerary days array

    func test_noDays_producesEmptyMapData() {
        let itinerary = OptimizerFixtures.itinerary(days: OptimizerFixtures.emptyDays)

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 0)
        XCTAssertFalse(data.hasMultipleDays)
    }
}
