import XCTest
@testable import TripClipApp

/// `OptimizerConfigurationStore` — depolama/izolasyon mantığı,
/// `TripOptimizerConfigViewModel`'den tamamen bağımsız test ediliyor (bkz.
/// docs/ios-trip-optimizer.md "Persistent Optimizer Configuration").
/// Geri yükleme/uzlaştırma (reconciliation) mantığı burada DEĞİL —
/// `TripOptimizerConfigViewModelTests.swift`'te, çünkü o mantık
/// `TripOptimizerConfigViewModel.reconciled(saved:availablePlaceIDs:)`'de
/// yaşıyor, bu store yalnızca ham (zaten geçerli) bir değeri saklar/döner.
@MainActor
final class OptimizerConfigurationStoreTests: XCTestCase {

    private func configuration(
        selected: Set<Int> = [1, 2], duration: Int? = 3,
        start: ClockTime = .defaultStart, end: ClockTime = .defaultEnd,
        date: PlanningDate? = nil, mode: OptimizerTransportMode = .automobile
    ) -> OptimizerConfiguration {
        OptimizerConfiguration(
            selectedPlaceIDs: selected, durationDays: duration,
            preferredStartTime: start, preferredEndTime: end,
            startDate: date, transportMode: mode
        )
    }

    // MARK: - Basic storage

    func test_configuration_forUnknownTrip_returnsNil() {
        let store = OptimizerConfigurationStore()
        XCTAssertNil(store.configuration(for: 1))
    }

    func test_save_thenConfiguration_returnsExactlyWhatWasSaved() {
        let store = OptimizerConfigurationStore()
        let config = configuration(selected: [7, 8], duration: 5, mode: .walking)

        store.save(config, for: 1)

        XCTAssertEqual(store.configuration(for: 1), config)
    }

    func test_save_overwritesPreviousConfiguration_forSameTrip() {
        let store = OptimizerConfigurationStore()
        store.save(configuration(selected: [1], duration: 1), for: 1)
        store.save(configuration(selected: [2], duration: 2), for: 1)

        XCTAssertEqual(store.configuration(for: 1)?.selectedPlaceIDs, [2])
        XCTAssertEqual(store.configuration(for: 1)?.durationDays, 2)
    }

    func test_remove_deletesConfiguration() {
        let store = OptimizerConfigurationStore()
        store.save(configuration(), for: 1)
        store.remove(for: 1)

        XCTAssertNil(store.configuration(for: 1))
    }

    // MARK: - Trip isolation (CRITICAL)

    func test_differentTrips_haveIndependentConfigurations() {
        let store = OptimizerConfigurationStore()
        let configA = configuration(selected: [1, 2], duration: 3, mode: .walking)
        let configB = configuration(selected: [7, 8], duration: 1, mode: .automobile)

        store.save(configA, for: 42)
        store.save(configB, for: 91)

        XCTAssertEqual(store.configuration(for: 42), configA)
        XCTAssertEqual(store.configuration(for: 91), configB)
    }

    func test_savingForOneTrip_neverLeaksIntoAnother() {
        let store = OptimizerConfigurationStore()
        store.save(configuration(selected: [1, 2]), for: 42)

        XCTAssertNil(store.configuration(for: 91), "Trip 42'nin yapılandırması trip 91'de asla görünmemeli")
    }

    /// A → B → tekrar A: A'nın yapılandırması B'nin ziyaretinden
    /// ETKİLENMEMİŞ olmalı.
    func test_switchingBetweenTrips_thenReturning_restoresOriginalConfiguration() {
        let store = OptimizerConfigurationStore()
        let configA = configuration(selected: [1, 2], duration: 3, mode: .walking)
        let configB = configuration(selected: [7, 8], duration: 1, mode: .automobile)

        store.save(configA, for: 42)
        store.save(configB, for: 91)

        XCTAssertEqual(store.configuration(for: 42), configA)
        XCTAssertEqual(store.configuration(for: 91), configB)
        // B'ye bakmak A'yı bozmamış olmalı.
        XCTAssertEqual(store.configuration(for: 42), configA)
    }

    // MARK: - updateTransportMode (Persistent Optimizer Transport Mode Sync)

    /// Bu trip için ZATEN bir yapılandırma varsa yalnızca `transportMode`
    /// değişir — yer seçimi/süre/saat/tarih AYNEN kalır (haritadan mod
    /// değiştirmek bunları ETKİLEMEMELİ).
    func test_updateTransportMode_withExistingConfiguration_changesOnlyTransportMode() {
        let store = OptimizerConfigurationStore()
        let original = configuration(selected: [1, 2, 3], duration: 4, date: PlanningDate(year: 2026, month: 8, day: 20), mode: .automobile)
        store.save(original, for: 1)

        store.updateTransportMode(.walking, for: 1, fallbackSelectedPlaceIDs: [99])

        let updated = store.configuration(for: 1)
        XCTAssertEqual(updated?.transportMode, .walking)
        XCTAssertEqual(updated?.selectedPlaceIDs, [1, 2, 3], "Mod değişikliği yer seçimini etkilememeli")
        XCTAssertEqual(updated?.durationDays, 4, "Mod değişikliği süreyi etkilememeli")
        XCTAssertEqual(updated?.preferredStartTime, original.preferredStartTime, "Mod değişikliği saati etkilememeli")
        XCTAssertEqual(updated?.preferredEndTime, original.preferredEndTime, "Mod değişikliği saati etkilememeli")
        XCTAssertEqual(updated?.startDate, original.startDate, "Mod değişikliği tarihi etkilememeli")
    }

    /// Bu trip için HİÇ yapılandırma yoksa (ör. Itinerary History'den
    /// doğrudan `.viewSaved` — yapılandırma ekranı hiç ziyaret edilmemiş),
    /// çağıranın sağladığı `fallbackSelectedPlaceIDs` ile YENİ bir kayıt
    /// oluşturulur — BOŞ bir küme DEĞİL (aksi halde bu trip için daha sonra
    /// yapılandırma ekranı açıldığında tüm mekanlar yanlışlıkla
    /// deselected görünürdü, bkz. `reconciled`'in kesişim mantığı).
    func test_updateTransportMode_withNoExistingConfiguration_createsOneUsingFallbackPlaceIDs() {
        let store = OptimizerConfigurationStore()

        store.updateTransportMode(.walking, for: 7, fallbackSelectedPlaceIDs: [11, 22])

        let created = store.configuration(for: 7)
        XCTAssertEqual(created?.transportMode, .walking)
        XCTAssertEqual(created?.selectedPlaceIDs, [11, 22])
        XCTAssertNil(created?.durationDays)
    }

    /// Reopening: mod değişikliğinden sonra `configuration(for:)` her
    /// zaman EN SON yazılan modu döner (yapılandırma ekranı VE harita
    /// bunun üzerinden geri yükleme yapar).
    func test_updateTransportMode_thenReadingConfiguration_reflectsLatestMode() {
        let store = OptimizerConfigurationStore()
        store.updateTransportMode(.walking, for: 3, fallbackSelectedPlaceIDs: [1])

        XCTAssertEqual(store.configuration(for: 3)?.transportMode, .walking)
    }

    /// Art arda değişiklikler: yalnızca EN SON değer kalıcı olmalı.
    func test_updateTransportMode_calledRepeatedly_persistsOnlyLatestValue() {
        let store = OptimizerConfigurationStore()
        store.updateTransportMode(.walking, for: 1, fallbackSelectedPlaceIDs: [1])
        store.updateTransportMode(.automobile, for: 1, fallbackSelectedPlaceIDs: [1])
        store.updateTransportMode(.walking, for: 1, fallbackSelectedPlaceIDs: [1])

        XCTAssertEqual(store.configuration(for: 1)?.transportMode, .walking)
    }

    /// Trip izolasyonu: trip A için mod değişikliği trip B'yi ASLA
    /// etkilememeli.
    func test_updateTransportMode_forTripA_neverAffectsTripB() {
        let store = OptimizerConfigurationStore()
        store.save(configuration(mode: .walking), for: 91)

        store.updateTransportMode(.automobile, for: 42, fallbackSelectedPlaceIDs: [1])

        XCTAssertEqual(store.configuration(for: 91)?.transportMode, .walking, "Trip 42 için mod değişikliği trip 91'i etkilememeli")
    }

    /// A → B → tekrar A: A için mod değişikliği yaptıktan sonra B'yi
    /// değiştirmek, A'nın az önce yazdığı değeri BOZMAMALI.
    func test_updateTransportMode_tripIsolation_roundTrip() {
        let store = OptimizerConfigurationStore()

        store.updateTransportMode(.walking, for: 42, fallbackSelectedPlaceIDs: [1, 2])
        store.updateTransportMode(.automobile, for: 91, fallbackSelectedPlaceIDs: [7])

        XCTAssertEqual(store.configuration(for: 42)?.transportMode, .walking)
        XCTAssertEqual(store.configuration(for: 91)?.transportMode, .automobile)
    }

    /// Transit Transport Mode milestone'unun kendi Req 7 senaryosu: harita
    /// (`OptimizerRouteMapSection`) Transit'e geçtiğinde `updateTransportMode`
    /// AYNI mekanizmadan geçmeli — üçüncü bir case eklenmiş olması
    /// `updateTransportMode`'un kendi mantığını hiç DEĞİŞTİRMEMELİ (zaten
    /// `OptimizerTransportMode`, keyfi bir değer olarak akıyor, özel bir
    /// case ayrımı YOK).
    func test_updateTransportMode_toTransit_worksExactlyLikeOtherModes() {
        let store = OptimizerConfigurationStore()
        let original = configuration(selected: [1, 2], duration: 3, mode: .automobile)
        store.save(original, for: 1)

        store.updateTransportMode(.transit, for: 1, fallbackSelectedPlaceIDs: [99])

        let updated = store.configuration(for: 1)
        XCTAssertEqual(updated?.transportMode, .transit)
        XCTAssertEqual(updated?.selectedPlaceIDs, [1, 2], "Transit'e geçiş yer seçimini etkilememeli")
        XCTAssertEqual(updated?.durationDays, 3, "Transit'e geçiş süreyi etkilememeli")
    }
}
