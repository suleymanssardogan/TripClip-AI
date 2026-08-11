import XCTest
@testable import TripClipApp

/// `OptimizerSelectionStore` — depolama/izolasyon/doğrulama mantığı,
/// `TripOptimizerView`'dan tamamen bağımsız test ediliyor (bkz.
/// docs/ios-trip-optimizer.md "Persistent Optimizer Map Selection").
/// Bu dosya iki katmanı ayırıyor: HAM depolama (`store`/`rawSelection`,
/// doğrulama yapmaz) ve GEÇERLİ-hâle-getirme (`resolveSelection`, her zaman
/// verilen `Itinerary`'e karşı doğrular).
@MainActor
final class OptimizerSelectionStoreTests: XCTestCase {

    private func stop(placeId: Int, dayIndex: Int, orderIndex: Int) -> ItineraryStop {
        ItineraryStop(
            placeId: placeId, name: "Mekan \(placeId)", lat: 41.0, lng: 29.0,
            dayIndex: dayIndex, orderIndex: orderIndex,
            arrivalTime: nil, departureTime: nil, visitDurationMinutes: 30,
            travelTimeToNextMinutes: nil, travelDistanceToNextKm: nil
        )
    }

    private func itinerary(id: Int, days: [ItineraryDay]) -> Itinerary {
        Itinerary(
            id: id, tripId: 1, strategyName: "greedy_distance",
            optimizationScore: 90, totalDistanceKm: 10, totalTravelTimeMinutes: 20,
            warnings: [], createdAt: "2026-08-08T10:00:00", days: days
        )
    }

    // MARK: - Basic storage

    func test_rawSelection_forUnknownItinerary_returnsNil() {
        let store = OptimizerSelectionStore()
        XCTAssertNil(store.rawSelection(for: 1))
    }

    func test_store_thenRawSelection_returnsExactlyWhatWasStored() {
        let store = OptimizerSelectionStore()
        let selection = OptimizerSelection(dayIndex: 1, stopID: "1-0-5")

        store.store(selection, for: 1)

        XCTAssertEqual(store.rawSelection(for: 1), selection)
    }

    func test_store_updatesExistingSelection_forSameItinerary() {
        let store = OptimizerSelectionStore()
        store.store(OptimizerSelection(dayIndex: 0, stopID: "a"), for: 1)
        store.store(OptimizerSelection(dayIndex: 1, stopID: "b"), for: 1)

        XCTAssertEqual(store.rawSelection(for: 1), OptimizerSelection(dayIndex: 1, stopID: "b"))
    }

    func test_store_supportsNilDayIndexAndStopID() {
        let store = OptimizerSelectionStore()
        store.store(OptimizerSelection(dayIndex: nil, stopID: nil), for: 1)

        XCTAssertEqual(store.rawSelection(for: 1), OptimizerSelection(dayIndex: nil, stopID: nil))
    }

    // MARK: - Itinerary isolation (Req 3, CRITICAL)

    func test_differentItineraries_haveIndependentSelections() {
        let store = OptimizerSelectionStore()
        store.store(OptimizerSelection(dayIndex: 1, stopID: "10"), for: 42)
        store.store(OptimizerSelection(dayIndex: 0, stopID: "20"), for: 91)

        XCTAssertEqual(store.rawSelection(for: 42), OptimizerSelection(dayIndex: 1, stopID: "10"))
        XCTAssertEqual(store.rawSelection(for: 91), OptimizerSelection(dayIndex: 0, stopID: "20"))
    }

    func test_storingForOneItinerary_neverLeaksIntoAnother() {
        let store = OptimizerSelectionStore()
        store.store(OptimizerSelection(dayIndex: 1, stopID: "a"), for: 42)

        XCTAssertNil(store.rawSelection(for: 91), "Itinerary 42'nin seçimi itinerary 91'de asla görünmemeli")
    }

    /// A → B → tekrar A: A'nın seçimi B'nin ziyaretinden ETKİLENMEMİŞ
    /// olmalı — Req 13'ün kendi senaryosu.
    func test_switchingBetweenItineraries_thenReturning_restoresOriginalSelection() {
        let store = OptimizerSelectionStore()
        let itinA = itinerary(id: 42, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        let itinB = itinerary(id: 91, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 3, dayIndex: 0, orderIndex: 0)]),
        ])
        let stopA = itinA.days[1].stops[0].id
        let stopB = itinB.days[0].stops[0].id

        store.store(OptimizerSelection(dayIndex: 1, stopID: stopA), for: 42)
        store.store(OptimizerSelection(dayIndex: 0, stopID: stopB), for: 91)

        XCTAssertEqual(store.resolveSelection(for: itinA), OptimizerSelection(dayIndex: 1, stopID: stopA))
        XCTAssertEqual(store.resolveSelection(for: itinB), OptimizerSelection(dayIndex: 0, stopID: stopB))
        // A'ya geri dönüş — B'yi ziyaret etmek A'nın seçimini bozmamış olmalı.
        XCTAssertEqual(store.resolveSelection(for: itinA), OptimizerSelection(dayIndex: 1, stopID: stopA))
    }

    // MARK: - Validation: valid day + valid stop restores (Req 5)

    func test_resolveSelection_validDayAndStop_restoresExactly() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        let stopID = itin.days[1].stops[0].id
        store.store(OptimizerSelection(dayIndex: 1, stopID: stopID), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: 1, stopID: stopID))
    }

    func test_resolveSelection_noStoredSelection_returnsDefault() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
        ])

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection())
    }

    // MARK: - Validation: invalid day falls back to first available day

    func test_resolveSelection_invalidDay_fallsBackToFirstAvailableDay_noStop() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        store.store(OptimizerSelection(dayIndex: 5, stopID: nil), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: 0, stopID: nil))
    }

    // MARK: - Validation: deleted stop falls back to valid day, no stop

    func test_resolveSelection_deletedStop_keepsStoredDay_whenStillValid() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        // "1-0-999" hiçbir zaman var olmamış bir stopID (silinmiş durağı simüle ediyor).
        store.store(OptimizerSelection(dayIndex: 1, stopID: "1-0-999"), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: 1, stopID: nil))
    }

    func test_resolveSelection_deletedStop_andInvalidDay_fallsBackToFirstAvailableDay() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
        ])
        store.store(OptimizerSelection(dayIndex: 5, stopID: "5-0-999"), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: 0, stopID: nil))
    }

    // MARK: - Validation: stop moved to another day follows the stop (Req 6)

    /// Kayıtlı `dayIndex` başka bir günü işaret etse bile, `stopID` HÂLÂ
    /// itinerary'de bir yerde bulunuyorsa, geri yüklenen seçim durağın
    /// KENDİ güncel gününü kullanmalı — kayıtlı (bayat) günü DEĞİL.
    func test_resolveSelection_stopFoundUnderDifferentDayThanStored_followsTheStopsCurrentDay() {
        let store = OptimizerSelectionStore()
        let currentStop = stop(placeId: 99, dayIndex: 1, orderIndex: 0)
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [currentStop]),
        ])
        // Kayıtlı seçim eski/bayat bir `dayIndex: 0` taşıyor, ama
        // `stopID` gerçekte 1. günde bulunuyor.
        store.store(OptimizerSelection(dayIndex: 0, stopID: currentStop.id), for: 1)

        let resolved = store.resolveSelection(for: itin)
        XCTAssertEqual(resolved, OptimizerSelection(dayIndex: 1, stopID: currentStop.id))
    }

    // MARK: - Validation: empty itinerary

    func test_resolveSelection_emptyItinerary_producesNilNilRegardlessOfStoredSelection() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [])
        store.store(OptimizerSelection(dayIndex: 3, stopID: "3-0-1"), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: nil, stopID: nil))
    }

    // MARK: - Validation: stored "Tümü" (nil dayIndex) stays "Tümü"

    func test_resolveSelection_storedAllDays_staysAllDays() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 1, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
        ])
        store.store(OptimizerSelection(dayIndex: nil, stopID: nil), for: 1)

        XCTAssertEqual(store.resolveSelection(for: itin), OptimizerSelection(dayIndex: nil, stopID: nil))
    }

    // MARK: - Session behavior: outlives any single "screen visit"

    /// Req 14 "verify that two separate TripOptimizerView/ViewModel
    /// instances using the same store see the previous selection" — bu,
    /// EKRAN-ÖMÜRLÜ değil OTURUM-ÖMÜRLÜ olduğunun asıl kanıtı: aynı
    /// `OptimizerSelectionStore` örneği üzerinde, ayrı ayrı iki "ziyaret"i
    /// (iki bağımsız `store`/`resolveSelection` çağrı dizisi) simüle
    /// ediyoruz — TEK bir View/ViewModel örneğine bağlı bir state değil.
    func test_sameStoreInstance_secondVisit_seesFirstVisitsSelection() {
        let store = OptimizerSelectionStore()
        let itin = itinerary(id: 7, days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        let stopID = itin.days[1].stops[0].id

        // "Birinci ziyaret" — kullanıcı Day 2 / bir durak seçiyor, ekrandan çıkıyor.
        store.store(OptimizerSelection(dayIndex: 1, stopID: stopID), for: itin.id)

        // "İkinci ziyaret" — YENİ bir TripOptimizerView/ViewModel örneği
        // (burada yalnızca yeni bir `resolveSelection` çağrısıyla temsil
        // ediliyor) AYNI store'u kullanıyor.
        let restoredOnSecondVisit = store.resolveSelection(for: itin)

        XCTAssertEqual(restoredOnSecondVisit, OptimizerSelection(dayIndex: 1, stopID: stopID))
    }
}
