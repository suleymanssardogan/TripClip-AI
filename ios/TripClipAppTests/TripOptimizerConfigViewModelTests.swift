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

    /// Overnight Time Ranges milestone: `end < start` artık GEÇERSİZ DEĞİL
    /// — gece yarısını aşan bir planlama penceresi anlamına gelir (bkz.
    /// docs/ios-trip-optimizer.md "Overnight Time Ranges"). Eski test adı
    /// ("_false_") artık YANLIŞ olurdu, bu yüzden davranışı doğru
    /// yansıtacak şekilde yeniden adlandırıldı.
    func test_isTimeRangeValid_true_whenStartAfterEnd_overnightRange() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 19, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 9, minute: 0))
        XCTAssertTrue(vm.isTimeRangeValid)
    }

    /// Milestone'un kendi asgari sözleşmesi: 18:00 → 01:00 ve 23:30 → 03:00
    /// ikisi de geçerli (overnight) aralıklar.
    func test_isTimeRangeValid_true_forOvernightRanges() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])

        vm.setPreferredStartTime(ClockTime(hour: 18, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 1, minute: 0))
        XCTAssertTrue(vm.isTimeRangeValid, "18:00 → 01:00 geçerli olmalı")

        vm.setPreferredStartTime(ClockTime(hour: 23, minute: 30))
        vm.setPreferredEndTime(ClockTime(hour: 3, minute: 0))
        XCTAssertTrue(vm.isTimeRangeValid, "23:30 → 03:00 geçerli olmalı")
    }

    /// `canOptimize` overnight bir aralıkla ENGELLENMEMELİ — yalnızca eşit
    /// değerler hâlâ optimize'ı engeller.
    func test_canOptimize_isTrue_withOvernightTimeRange() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 18, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 1, minute: 0))
        XCTAssertTrue(vm.canOptimize)
    }

    /// Req 4 "Optimize must not execute while the configuration is
    /// invalid": geçerli bir mekan seçimi olsa bile, geçersiz bir zaman
    /// aralığı `canOptimize`'ı false yapmalı.
    /// Overnight Time Ranges milestone: `20:00 → 08:00` ARTIK geçerli bir
    /// overnight aralık olduğundan bu testin eski girdisi (`canOptimize`'ı
    /// engellemesi beklenen) artık YANLIŞ bir varsayım taşırdı — tek
    /// gerçekten geçersiz durum (eşit değerler) kullanacak şekilde
    /// güncellendi (bkz. docs/ios-trip-optimizer.md "Overnight Time
    /// Ranges").
    func test_canOptimize_isFalse_whenTimeRangeInvalid_evenWithPlacesSelected() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        XCTAssertTrue(vm.canOptimize)   // başlangıç durumu geçerli

        let same = ClockTime(hour: 20, minute: 0)
        vm.setPreferredStartTime(same)
        vm.setPreferredEndTime(same)

        XCTAssertFalse(vm.canOptimize)
        XCTAssertFalse(vm.selectedPlaceIDs.isEmpty, "Mekan seçimi hâlâ dolu — engelleyen yalnızca zaman aralığı")
    }

    /// Yeni: overnight bir aralık `canOptimize`'ı ENGELLEMEMELİ.
    func test_canOptimize_isTrue_whenTimeRangeIsOvernight() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.setPreferredStartTime(ClockTime(hour: 20, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 8, minute: 0))

        XCTAssertTrue(vm.canOptimize)
    }

    func test_canOptimize_isTrue_whenPlacesSelectedAndTimeRangeValid() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 10, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 16, minute: 0))
        XCTAssertTrue(vm.canOptimize)
    }

    // MARK: - Preferred start date (Trip Planning Date milestone)

    /// Req 3/4: backend'de `start_date` için sabit bir varsayılan YOK
    /// (`preferred_start_time`/`end_time`'ın aksine) — bu yüzden
    /// `durationDays` gibi `nil` ("Otomatik"/"tarih yok") ile başlar.
    func test_defaultPreferredStartDate_isNil() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertNil(vm.preferredStartDate)
    }

    func test_setPreferredStartDate_setsTheDate() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))
        XCTAssertEqual(vm.preferredStartDate, PlanningDate(year: 2026, month: 9, day: 1))
    }

    /// `nil` geçmek "Otomatik"a döner — kullanıcı tarih seçicisini kapatırsa.
    func test_setPreferredStartDate_withNil_clearsTheDate() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))
        vm.setPreferredStartDate(nil)
        XCTAssertNil(vm.preferredStartDate)
    }

    /// Tarih ayarlamak diğer hiçbir state'e (seçim/süre/saatler) dokunmamalı.
    func test_setPreferredStartDate_doesNotAffectOtherState() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.toggle(2)
        vm.setPreferredStartTime(ClockTime(hour: 7, minute: 0))

        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))

        XCTAssertFalse(vm.isSelected(2))
        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 7, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, .defaultEnd)
    }

    /// Req 4: tarih, `canOptimize`'ı hiçbir zaman ETKİLEMEZ — yer seçimi ve
    /// zaman aralığı geçerliyse, tarih ne olursa olsun (belirtilmiş ya da
    /// "Otomatik") optimize edilebilir olmalı.
    func test_canOptimize_isUnaffectedByPreferredStartDate() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertTrue(vm.canOptimize)

        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))
        XCTAssertTrue(vm.canOptimize)

        vm.setPreferredStartDate(nil)
        XCTAssertTrue(vm.canOptimize)
    }

    // MARK: - Persistent Optimizer Configuration — restoration (Req 8/9)

    /// Kayıtlı bir yapılandırma YOKSA (ilk açılış), bugünkü (bu milestone
    /// ÖNCESİ) varsayılan davranışın AYNISI üretilmeli (Req 15).
    func test_noSavedConfiguration_usesExistingDefaults() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)

        XCTAssertEqual(vm.selectedCount, 2)
        XCTAssertNil(vm.durationDays)
        XCTAssertEqual(vm.preferredStartTime, .defaultStart)
        XCTAssertEqual(vm.preferredEndTime, .defaultEnd)
        XCTAssertNil(vm.preferredStartDate)
    }

    /// Kayıtlı bir yapılandırma VARSA ve hâlâ tamamen geçerliyse, AYNEN
    /// geri yüklenmeli.
    func test_savedConfiguration_restoredExactly() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1, 2], durationDays: 4,
                preferredStartTime: ClockTime(hour: 10, minute: 0),
                preferredEndTime: ClockTime(hour: 20, minute: 0),
                startDate: PlanningDate(year: 2026, month: 9, day: 1),
                transportMode: .walking
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)

        XCTAssertEqual(vm.selectedPlaceIDs, [1, 2])
        XCTAssertEqual(vm.durationDays, 4)
        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 10, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, ClockTime(hour: 20, minute: 0))
        XCTAssertEqual(vm.preferredStartDate, PlanningDate(year: 2026, month: 9, day: 1))
    }

    /// Spesifikasyonun kendi örneği: saved [1,2,3,4], current trip [1,2,4,5]
    /// → restore [1,2,4] — kaldırılmış ID (3) düşer, YENİ mekan (5) OTOMATİK
    /// seçilmez.
    func test_savedSelection_reconciledAgainstCurrentTrip_removedIDsDropped_newIDsNotAutoSelected() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1, 2, 3, 4], durationDays: nil,
                preferredStartTime: .defaultStart, preferredEndTime: .defaultEnd,
                startDate: nil, transportMode: .automobile
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(
            tripID: 1, stops: [stop(1), stop(2), stop(4), stop(5)], configStore: store
        )

        XCTAssertEqual(vm.selectedPlaceIDs, [1, 2, 4])
        XCTAssertFalse(vm.isSelected(5), "Daha önce hiç görülmemiş mekan otomatik seçilmemeli")
    }

    /// Kaydedilmiş süre geçerli aralığın dışındaysa (savunma amaçlı —
    /// pratikte VM zaten hep aralık içinde tutar) mevcut sınırlara kırpılır.
    func test_savedDuration_outOfRange_isClampedToValidBounds() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1], durationDays: 999,
                preferredStartTime: .defaultStart, preferredEndTime: .defaultEnd,
                startDate: nil, transportMode: .automobile
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(vm.durationDays, TripOptimizerConfigViewModel.durationRange.upperBound)
    }

    /// Kaydedilmiş bir zaman aralığı geçersizse (yalnızca eşit değerler
    /// geçersiz — bkz. `isTimeRangeValid`), mevcut geçerli varsayılanlara
    /// güvenle düşülür.
    func test_savedInvalidTimeRange_fallsBackToDefaults() {
        let store = OptimizerConfigurationStore()
        let same = ClockTime(hour: 15, minute: 0)
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1], durationDays: nil,
                preferredStartTime: same, preferredEndTime: same,
                startDate: nil, transportMode: .automobile
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(vm.preferredStartTime, .defaultStart)
        XCTAssertEqual(vm.preferredEndTime, .defaultEnd)
        XCTAssertTrue(vm.isTimeRangeValid)
    }

    /// Geçerli bir overnight aralık (`end < start`) AYNEN geri yüklenmeli —
    /// eski `end > start` kısıtı YENİDEN devreye girmemeli.
    func test_savedOvernightTimeRange_restoredExactly() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1], durationDays: nil,
                preferredStartTime: ClockTime(hour: 18, minute: 0),
                preferredEndTime: ClockTime(hour: 1, minute: 0),
                startDate: nil, transportMode: .automobile
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 18, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, ClockTime(hour: 1, minute: 0))
        XCTAssertTrue(vm.isTimeRangeValid)
    }

    func test_savedStartDate_restored() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1], durationDays: nil,
                preferredStartTime: .defaultStart, preferredEndTime: .defaultEnd,
                startDate: PlanningDate(year: 2026, month: 12, day: 25), transportMode: .automobile
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(vm.preferredStartDate, PlanningDate(year: 2026, month: 12, day: 25))
    }

    func test_savedTransportMode_restored() {
        let store = OptimizerConfigurationStore()
        store.save(
            OptimizerConfiguration(
                selectedPlaceIDs: [1], durationDays: nil,
                preferredStartTime: .defaultStart, preferredEndTime: .defaultEnd,
                startDate: nil, transportMode: .walking
            ),
            for: 1
        )

        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(vm.transportMode, .walking)
    }

    /// Persistent Optimizer Transport Mode Sync: bu trip'in yapılandırma
    /// ekranı hiç ziyaret EDİLMEDEN önce (`.viewSaved` akışı — Itinerary
    /// History'den doğrudan açılmış), yalnızca haritadan
    /// `OptimizerConfigurationStore.updateTransportMode` çağrılmış olsun —
    /// bu, `OptimizerRouteMapSection`'ın `onTransportModeChanged`
    /// callback'inin `TripOptimizerView` üzerinden tetiklediği ile AYNI
    /// çağrı. Yapılandırma ekranı DAHA SONRA açıldığında, `selectedPlaceIDs`
    /// BOŞ görünmemeli — haritanın sağladığı fallback ID'ler restore
    /// edilmeli (aksi halde kullanıcı tüm mekanların yanlışlıkla
    /// deselected olduğunu görürdü).
    func test_mapOnlyTransportModeChange_beforeAnyConfigScreenVisit_doesNotEmptySelectionOnLaterVisit() {
        let store = OptimizerConfigurationStore()

        // Harita (yapılandırma ekranı hiç açılmadan) mod değiştirir —
        // görüntülenen itinerary'nin durakları [1, 2] olsun.
        store.updateTransportMode(.walking, for: 1, fallbackSelectedPlaceIDs: [1, 2])

        // Kullanıcı ŞİMDİ yapılandırma ekranını açar.
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)

        XCTAssertEqual(vm.selectedPlaceIDs, [1, 2], "Haritanın fallback ID'leri restore edilmeli, boş küme DEĞİL")
        XCTAssertEqual(vm.transportMode, .walking)
    }

    // MARK: - Persistent Optimizer Configuration — save-on-change (Req 10)

    func test_togglingSelection_updatesStoredConfiguration() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)

        vm.toggle(2)

        XCTAssertEqual(store.configuration(for: 1)?.selectedPlaceIDs, [1])
    }

    func test_changingDuration_updatesStoredConfiguration() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        vm.incrementDuration()
        vm.incrementDuration()

        XCTAssertEqual(store.configuration(for: 1)?.durationDays, 2)
    }

    func test_changingPreferredTimes_updatesStoredConfiguration() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        vm.setPreferredStartTime(ClockTime(hour: 20, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 2, minute: 0))

        XCTAssertEqual(store.configuration(for: 1)?.preferredStartTime, ClockTime(hour: 20, minute: 0))
        XCTAssertEqual(store.configuration(for: 1)?.preferredEndTime, ClockTime(hour: 2, minute: 0))
    }

    func test_changingStartDate_updatesStoredConfiguration() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 6, day: 15))

        XCTAssertEqual(store.configuration(for: 1)?.startDate, PlanningDate(year: 2026, month: 6, day: 15))
    }

    func test_changingTransportMode_updatesStoredConfiguration() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        vm.setTransportMode(.walking)

        XCTAssertEqual(store.configuration(for: 1)?.transportMode, .walking)
    }

    // MARK: - Persistent Optimizer Configuration — trip isolation (Req 12)

    /// Trip A ve Trip B, AYNI paylaşılan store'u kullanan İKİ AYRI
    /// `TripOptimizerConfigViewModel` örneği ile yapılandırılır — A'nın
    /// ayarları B'de asla görünmemeli.
    func test_tripIsolation_configurationForTripA_neverAppearsOnTripB() {
        let store = OptimizerConfigurationStore()
        let vmA = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)
        vmA.deselectAll()
        vmA.toggle(1)
        vmA.incrementDuration()
        vmA.incrementDuration()
        vmA.incrementDuration()
        vmA.setTransportMode(.walking)

        let vmB = TripOptimizerConfigViewModel(tripID: 2, stops: [stop(7), stop(8)], configStore: store)

        XCTAssertEqual(vmB.selectedCount, 2, "Trip B kendi varsayılanıyla (tümü seçili) başlamalı")
        XCTAssertNil(vmB.durationDays)
        XCTAssertEqual(vmB.transportMode, .automobile)
    }

    /// A → B → tekrar A (yeni bir ViewModel örneği olarak, "ekranı tekrar
    /// açmak"ı simüle eder) — A'nın yapılandırması B'nin ziyaretinden
    /// ETKİLENMEMİŞ olmalı.
    func test_tripIsolation_reopeningTripA_afterVisitingTripB_restoresTripAsConfiguration() {
        let store = OptimizerConfigurationStore()

        let firstVisitA = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)
        firstVisitA.deselectAll()
        firstVisitA.toggle(2)
        firstVisitA.setTransportMode(.walking)

        // Trip B'yi ziyaret et.
        let visitB = TripOptimizerConfigViewModel(tripID: 2, stops: [stop(9)], configStore: store)
        visitB.setTransportMode(.automobile)

        // Trip A'yı YENİDEN aç (yeni bir ViewModel örneği — "ekranı
        // tekrar açmak").
        let secondVisitA = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1), stop(2)], configStore: store)

        XCTAssertEqual(secondVisitA.selectedPlaceIDs, [2])
        XCTAssertEqual(secondVisitA.transportMode, .walking)
    }

    // MARK: - Optimizer Configuration Transport Mode Picker

    func test_defaultTransportMode_isAutomobile() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertEqual(vm.transportMode, .automobile)
    }

    func test_setTransportMode_walking_updatesViewModel() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setTransportMode(.walking)
        XCTAssertEqual(vm.transportMode, .walking)
    }

    func test_setTransportMode_automobile_updatesViewModel() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setTransportMode(.walking)
        vm.setTransportMode(.automobile)
        XCTAssertEqual(vm.transportMode, .automobile)
    }

    /// Req 11 "Map receives the restored mode correctly": `TripOptimizerView`
    /// haritayı kurarken tam olarak `configStore.configuration(for:)?.transportMode`'u
    /// okuyor (bkz. o dosyanın `resultContent`'i) — bu yüzden buradaki
    /// doğru davranış, config ekranındaki değişikliğin AYNI store
    /// kaydından okunabilir olmasıdır; harita View'ı burada değil.
    func test_setTransportMode_valueReadableFromStore_asMapWouldReadIt() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 5, stops: [stop(1)], configStore: store)

        vm.setTransportMode(.walking)

        XCTAssertEqual(store.configuration(for: 5)?.transportMode, .walking)
    }

    func test_changingTransportMode_doesNotModifySelectedPlaces() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.toggle(2)
        let before = vm.selectedPlaceIDs

        vm.setTransportMode(.walking)

        XCTAssertEqual(vm.selectedPlaceIDs, before)
    }

    func test_changingTransportMode_doesNotModifyDuration() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.incrementDuration()
        vm.incrementDuration()

        vm.setTransportMode(.walking)

        XCTAssertEqual(vm.durationDays, 2)
    }

    func test_changingTransportMode_doesNotModifyPreferredTimes() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 20, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 2, minute: 0))

        vm.setTransportMode(.walking)

        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 20, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, ClockTime(hour: 2, minute: 0))
    }

    func test_changingTransportMode_doesNotModifyPreferredStartDate() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))

        vm.setTransportMode(.walking)

        XCTAssertEqual(vm.preferredStartDate, PlanningDate(year: 2026, month: 9, day: 1))
    }

    /// Req 6, ilk desen: A → Yürüyüş, B → Araba, A → Yürüyüş (A'nın
    /// modu B'nin ziyaretinden ETKİLENMEMİŞ olmalı, her adım YENİ bir
    /// ViewModel örneğiyle — "ekranı tekrar açmak"ı simüle eder).
    func test_transportModeIsolation_walkingThenAutomobile_roundTrip() {
        let store = OptimizerConfigurationStore()

        let visitA1 = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)
        visitA1.setTransportMode(.walking)

        let visitB = TripOptimizerConfigViewModel(tripID: 2, stops: [stop(9)], configStore: store)
        visitB.setTransportMode(.automobile)

        let visitA2 = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(visitA2.transportMode, .walking, "Trip A'nın modu Trip B ziyaretinden etkilenmemeli")
        XCTAssertEqual(store.configuration(for: 2)?.transportMode, .automobile)
    }

    /// Req 6, ters desen: A → Araba, B → Yürüyüş, A → Araba.
    func test_transportModeIsolation_automobileThenWalking_roundTrip() {
        let store = OptimizerConfigurationStore()

        let visitA1 = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)
        visitA1.setTransportMode(.automobile)

        let visitB = TripOptimizerConfigViewModel(tripID: 2, stops: [stop(9)], configStore: store)
        visitB.setTransportMode(.walking)

        let visitA2 = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(visitA2.transportMode, .automobile, "Trip A'nın modu Trip B ziyaretinden etkilenmemeli")
        XCTAssertEqual(store.configuration(for: 2)?.transportMode, .walking)
    }

    // MARK: - Transit Transport Mode

    /// Req 16: varsayılan mod otomobil KALMALI — Transit'in eklenmesi
    /// mevcut varsayılanı DEĞİŞTİRMEMELİ.
    func test_defaultTransportMode_stillAutomobile_afterTransitAdded() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        XCTAssertEqual(vm.transportMode, .automobile)
    }

    /// Req 17: Transit seçilebilir olmalı.
    func test_setTransportMode_transit_updatesViewModel() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setTransportMode(.transit)
        XCTAssertEqual(vm.transportMode, .transit)
    }

    /// Req 18: Transit seçimi kalıcı olmalı.
    func test_setTransportMode_transit_persistsToStore() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        vm.setTransportMode(.transit)

        XCTAssertEqual(store.configuration(for: 1)?.transportMode, .transit)
    }

    /// Req 19: ViewModel yeniden oluşturulduğunda (ekranı tekrar açmak)
    /// Transit geri yüklenmeli.
    func test_transit_restoresAfterViewModelRecreation() {
        let store = OptimizerConfigurationStore()
        let firstVisit = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)
        firstVisit.setTransportMode(.transit)

        let secondVisit = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)

        XCTAssertEqual(secondVisit.transportMode, .transit)
    }

    /// Req 20: Trip A/B Transit yapılandırmaları izole kalmalı.
    func test_transit_tripIsolation() {
        let store = OptimizerConfigurationStore()
        let vmA = TripOptimizerConfigViewModel(tripID: 1, stops: [stop(1)], configStore: store)
        vmA.setTransportMode(.transit)

        let vmB = TripOptimizerConfigViewModel(tripID: 2, stops: [stop(9)], configStore: store)

        XCTAssertEqual(vmB.transportMode, .automobile, "Trip B, Trip A'nın Transit seçiminden etkilenmemeli")
        XCTAssertEqual(store.configuration(for: 1)?.transportMode, .transit)
    }

    /// Req 11 (map-restoration semantiği, transit için): Transit de tıpkı
    /// walking/automobile gibi `OptimizerConfigurationStore`'dan okunabilir
    /// olmalı — `TripOptimizerView`'ın haritayı kurarken okuduğu AYNI yol.
    func test_setTransportMode_transit_valueReadableFromStore_asMapWouldReadIt() {
        let store = OptimizerConfigurationStore()
        let vm = TripOptimizerConfigViewModel(tripID: 5, stops: [stop(1)], configStore: store)

        vm.setTransportMode(.transit)

        XCTAssertEqual(store.configuration(for: 5)?.transportMode, .transit)
    }

    // MARK: - Transit Transport Mode — non-interference (Req 21-24)

    func test_changingToTransit_doesNotModifySelectedPlaces() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1), stop(2)])
        vm.toggle(2)
        let before = vm.selectedPlaceIDs

        vm.setTransportMode(.transit)

        XCTAssertEqual(vm.selectedPlaceIDs, before)
    }

    func test_changingToTransit_doesNotModifyDuration() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.incrementDuration()
        vm.incrementDuration()

        vm.setTransportMode(.transit)

        XCTAssertEqual(vm.durationDays, 2)
    }

    func test_changingToTransit_doesNotModifyPreferredTimes() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartTime(ClockTime(hour: 20, minute: 0))
        vm.setPreferredEndTime(ClockTime(hour: 2, minute: 0))

        vm.setTransportMode(.transit)

        XCTAssertEqual(vm.preferredStartTime, ClockTime(hour: 20, minute: 0))
        XCTAssertEqual(vm.preferredEndTime, ClockTime(hour: 2, minute: 0))
    }

    func test_changingToTransit_doesNotModifyPreferredStartDate() {
        let vm = TripOptimizerConfigViewModel(stops: [stop(1)])
        vm.setPreferredStartDate(PlanningDate(year: 2026, month: 9, day: 1))

        vm.setTransportMode(.transit)

        XCTAssertEqual(vm.preferredStartDate, PlanningDate(year: 2026, month: 9, day: 1))
    }
}
