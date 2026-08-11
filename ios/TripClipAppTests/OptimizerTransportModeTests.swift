import XCTest
import MapKit
@testable import TripClipApp

/// `OptimizerTransportMode` — kendi başına, `OptimizerRouteCalculator`'dan
/// bağımsız test edilen saf model: her `case`'in görünen başlığı,
/// erişilebilirlik etiketi, ve `MKDirectionsTransportType` eşlemesi.
final class OptimizerTransportModeTests: XCTestCase {

    // MARK: - Titles

    func test_automobile_title_isAraba() {
        XCTAssertEqual(OptimizerTransportMode.automobile.title, "Araba")
    }

    func test_walking_title_isYuruyus() {
        XCTAssertEqual(OptimizerTransportMode.walking.title, "Yürüyüş")
    }

    // MARK: - Accessibility labels

    func test_automobile_accessibilityLabel_isDescriptive() {
        XCTAssertEqual(OptimizerTransportMode.automobile.accessibilityLabel, "Araba ile rota")
    }

    func test_walking_accessibilityLabel_isDescriptive() {
        XCTAssertEqual(OptimizerTransportMode.walking.accessibilityLabel, "Yürüyüş rotası")
    }

    func test_transit_accessibilityLabel_isDescriptive() {
        XCTAssertEqual(OptimizerTransportMode.transit.accessibilityLabel, "Toplu taşıma rotası")
    }

    // MARK: - MapKit mapping (Req: "automobile → .automobile, walking → .walking, transit → .transit")

    func test_automobile_mapsToMKDirectionsTransportTypeAutomobile() {
        XCTAssertEqual(OptimizerTransportMode.automobile.mapKitType, .automobile)
    }

    func test_walking_mapsToMKDirectionsTransportTypeWalking() {
        XCTAssertEqual(OptimizerTransportMode.walking.mapKitType, .walking)
    }

    func test_transit_mapsToMKDirectionsTransportTypeTransit() {
        XCTAssertEqual(OptimizerTransportMode.transit.mapKitType, .transit)
    }

    // MARK: - Transit Transport Mode (v18)

    func test_transit_title_isTopluTasima() {
        XCTAssertEqual(OptimizerTransportMode.transit.title, "Toplu Taşıma")
    }

    func test_transit_symbolName_isTramFill() {
        XCTAssertEqual(OptimizerTransportMode.transit.symbolName, "tram.fill")
    }

    func test_transit_rawValue_isStable() {
        XCTAssertEqual(OptimizerTransportMode.transit.rawValue, "transit")
    }

    // MARK: - CaseIterable (selector UI iterates over this)

    func test_allCases_containsAutomobileWalkingAndTransit_inThatOrder() {
        XCTAssertEqual(OptimizerTransportMode.allCases, [.automobile, .walking, .transit])
    }
}
