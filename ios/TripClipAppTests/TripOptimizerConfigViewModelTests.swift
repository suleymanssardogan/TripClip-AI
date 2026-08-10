import XCTest
@testable import TripClipApp

/// TripOptimizerConfigViewModel birim testleri — tamamen yerel/senkron durum,
/// AĞ ÇAĞRISI YOK (bkz. TripOptimizerConfigViewModel'in kendi docstring'i:
/// "Selection is only optimizer input"). Gerçek optimize isteği yalnızca
/// TripOptimizerViewModel.optimize çağrıldığında gider — bkz.
/// TripOptimizerViewModelTests.test_optimize_forwardsDurationDays_whenProvided.
@MainActor
final class TripOptimizerConfigViewModelTests: XCTestCase {

    private func stop(_ placeId: Int, name: String = "Mekan", city: String? = "İstanbul") -> TripStop {
        TripStop(placeId: placeId, name: name, latitude: 41.0, longitude: 29.0, city: city, category: nil, dayIndex: 0, orderIndex: placeId)
    }

    // MARK: - Default selection (spesifikasyonun 1. gereksinimi)

    func test_defaultSelection_includesAllStops() {
        let stops = [stop(1), stop(2), stop(3)]
        let vm = TripOptimizerConfigViewModel(stops: stops)

        XCTAssertEqual(vm.selectedCount, 3)
        XCTAssertTrue(vm.isSelected(1))
        XCTAssertTrue(vm.isSelected(2))
        XCTAssertTrue(vm.isSelected(3))
    }

    func test_defaultDuration_isAutomatic() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertNil(vm.durationDays)
    }

    func test_emptyStops_producesEmptySelection() {
        let vm = TripOptimizerConfigViewModel(stops: [])
        XCTAssertEqual(vm.selectedCount, 0)
        XCTAssertFalse(vm.canOptimize)
    }

    // MARK: - Selecting/deselecting places

    func test_toggle_deselectsASelectedPlace() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.toggle(1)
        XCTAssertFalse(vm.isSelected(1))
        XCTAssertTrue(vm.isSelected(2))
        XCTAssertEqual(vm.selectedCount, 1)
    }

    func test_toggle_reselectsADeselectedPlace() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.toggle(1)
        vm.toggle(1)
        XCTAssertTrue(vm.isSelected(1))
        XCTAssertEqual(vm.selectedCount, 1)
    }

    func test_deselectAll_clearsSelection() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2), stop(3)])
        vm.deselectAll()
        XCTAssertEqual(vm.selectedCount, 0)
        XCTAssertFalse(vm.canOptimize)
    }

    func test_selectAll_afterDeselectAll_restoresFullSelection() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.deselectAll()
        vm.selectAll()
        XCTAssertEqual(vm.selectedCount, 2)
    }

    // MARK: - Selected count

    func test_selectedCount_reflectsPartialSelection() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2), stop(3), stop(4)])
        vm.toggle(2)
        vm.toggle(4)
        XCTAssertEqual(vm.selectedCount, 2)
    }

    // MARK: - Zero-selection validation (spesifikasyonun 5. gereksinimi)

    func test_canOptimize_isFalse_whenNoPlacesSelected() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.deselectAll()
        XCTAssertFalse(vm.canOptimize)
    }

    func test_canOptimize_isTrue_withExactlyOnePlaceSelected() {
        // Tek mekan seçimi geçerli olmalı — yalnızca SIFIR seçim engellenir.
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.deselectAll()
        vm.toggle(1)
        XCTAssertTrue(vm.canOptimize)
        XCTAssertEqual(vm.selectedCount, 1)
    }

    // MARK: - Duration bounds (spesifikasyonun 2./5. gereksinimi)

    func test_incrementDuration_fromAutomatic_goesToOne() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.incrementDuration()
        XCTAssertEqual(vm.durationDays, 1)
    }

    func test_incrementDuration_stopsAtUpperBound() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        for _ in 0..<(TripOptimizerConfigViewModel.durationRange.upperBound + 5) {
            vm.incrementDuration()
        }
        XCTAssertEqual(vm.durationDays, TripOptimizerConfigViewModel.durationRange.upperBound)
    }

    func test_decrementDuration_fromOne_returnsToAutomatic() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.incrementDuration()  // -> 1
        vm.decrementDuration()  // -> nil (Otomatik)
        XCTAssertNil(vm.durationDays)
    }

    func test_decrementDuration_atAutomatic_staysAutomatic() {
        // UI hiçbir zaman 0 veya negatif bir değer üretemez.
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.decrementDuration()
        XCTAssertNil(vm.durationDays)
    }

    func test_durationDays_neverExceedsUpperBoundOrGoesBelowOne() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        for _ in 0..<50 { vm.incrementDuration() }
        XCTAssertLessThanOrEqual(vm.durationDays ?? 0, TripOptimizerConfigViewModel.durationRange.upperBound)
        for _ in 0..<50 { vm.decrementDuration() }
        if let days = vm.durationDays {
            XCTAssertGreaterThanOrEqual(days, TripOptimizerConfigViewModel.durationRange.lowerBound)
        }
    }

    // MARK: - Request construction: selected IDs preserve Trip order

    func test_selectedPlaceIDsInTripOrder_preservesOriginalStopOrder_notInsertionOrder() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(5), stop(2), stop(9)])
        vm.deselectAll()
        vm.toggle(9)  // ters sırayla seç
        vm.toggle(5)
        vm.toggle(2)

        // Set eklenme sırası korumaz, ama Trip'in kendi durak sırası (5,2,9)
        // korunmalı.
        XCTAssertEqual(vm.selectedPlaceIDsInTripOrder, [5, 2, 9])
    }

    func test_selectedPlaceIDsInTripOrder_excludesDeselectedPlaces() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2), stop(3)])
        vm.toggle(2)
        XCTAssertEqual(vm.selectedPlaceIDsInTripOrder, [1, 3])
    }
}
