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

    // MARK: - Preferred start/end time defaults (Req 3: match backend exactly)

    func test_defaultPreferredStartTime_matchesBackendDefault() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertEqual(vm.preferredStartTime, ClockTime.defaultStart)
        XCTAssertEqual(vm.preferredStartTime.apiValue, "09:00")
    }

    func test_defaultPreferredEndTime_matchesBackendDefault() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertEqual(vm.preferredEndTime, ClockTime.defaultEnd)
        XCTAssertEqual(vm.preferredEndTime.apiValue, "18:00")
    }

    func test_defaultTimeRange_isValid() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertTrue(vm.isTimeRangeValid)
    }

    // MARK: - Independent start/end time updates (spesifikasyonun kendi test gereksinimi)

    func test_setPreferredStartTime_updatesOnlyStartTime() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 7, minute: 30))

        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 7, minute: 30))
        XCTAssertEqual(vm.preferredEndTime, ClockTime.defaultEnd, "Yalnızca başlangıç değişmeli, bitiş etkilenmemeli")
    }

    func test_setPreferredEndTime_updatesOnlyEndTime() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredEndTime(ClockTime(hour: 21, minute: 15))

        XCTAssertEqual(vm.preferredEndTime, ClockTime(hour: 21, minute: 15))
        XCTAssertEqual(vm.preferredStartTime, ClockTime.defaultStart, "Yalnızca bitiş değişmeli, başlangıç etkilenmemeli")
    }

    func test_settingBothTimes_inSequence_eachSetterOnlyAffectsItsOwnField() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 6, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, ClockTime.defaultEnd)

        vm.setPreferredEndTime(ClockTime(hour: 23, minute: 0))
        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 6, minute: 0), "Önceki başlangıç ataması korunmalı")
    }

    // MARK: - Valid/invalid range (Req 4)

    func test_isTimeRangeValid_true_whenStartBeforeEnd() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 8, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 20, minute: 0))
        XCTAssertTrue(vm.isTimeRangeValid)
    }

    func test_isTimeRangeValid_false_whenStartEqualsEnd() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        let same = ClockTime(hour: 12, minute: 0)
        vm.setPreferredStartTime(same)
        vm.setPreferredEndTime(same)
        XCTAssertFalse(vm.isTimeRangeValid, "core-api aynı değerleri de reddeder (end > start, >= değil)")
    }

    func test_isTimeRangeValid_false_whenStartAfterEnd() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 19, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 9, minute: 0))
        XCTAssertFalse(vm.isTimeRangeValid)
    }

    /// Req 4 "Optimize must not execute while the configuration is
    /// invalid": geçerli bir mekan seçimi olsa bile, geçersiz bir zaman
    /// aralığı `canOptimize`'ı false yapmalı.
    func test_canOptimize_isFalse_whenTimeRangeInvalid_evenWithPlacesSelected() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        XCTAssertTrue(vm.canOptimize)   // başlangıç durumu geçerli

        vm.setPreferredStartTime(ClockTime(hour: 20, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 8, minute: 0))

        XCTAssertFalse(vm.canOptimize)
        XCTAssertFalse(vm.selectedPlaceIDs.isEmpty, "Mekan seçimi hâlâ dolu — engelleyen yalnızca zaman aralığı")
    }

    func test_canOptimize_isTrue_whenPlacesSelectedAndTimeRangeValid() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 10, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 16, minute: 0))
        XCTAssertTrue(vm.canOptimize)
    }
}
