import XCTest
import CoreLocation
@testable import TripClipApp

/// `OptimizerRouteCache` — kendi başına, `OptimizerRouteCalculator`'dan
/// bağımsız test edilen saklama/LRU davranışı. `OptimizerRouteCalculator`'ın
/// bu tipi NASIL kullandığı (bacak anahtarı üretimi, hangi durumlarda
/// yazıldığı/okunduğu) `OptimizerRouteCalculatorTests.swift`'te — burada
/// yalnızca `OptimizerRouteCache`'in kendi sözleşmesi: saklanan tam olarak
/// verilen `[CLLocationCoordinate2D]`'i geri döner, bulunamayan bir anahtar
/// `nil` döner, kapasite aşılınca en eski girdi atılır.
@MainActor
final class OptimizerRouteCacheTests: XCTestCase {

    private func coords(_ lat: Double) -> [CLLocationCoordinate2D] {
        [CLLocationCoordinate2D(latitude: lat, longitude: lat)]
    }

    // MARK: - Store / retrieve

    func test_coordinates_forUnknownKey_returnsNil() {
        let cache = OptimizerRouteCache()
        XCTAssertNil(cache.coordinates(for: "unknown"))
    }

    func test_store_thenCoordinates_returnsExactlyWhatWasStored() throws {
        let cache = OptimizerRouteCache()
        cache.store(coords(41.0), for: "leg-a")

        let retrieved = try XCTUnwrap(cache.coordinates(for: "leg-a"))
        XCTAssertEqual(retrieved.first?.latitude ?? -999, 41.0, accuracy: 0.0001)
    }

    func test_store_overwritesPreviousValueForSameKey() throws {
        let cache = OptimizerRouteCache()
        cache.store(coords(41.0), for: "leg-a")
        cache.store(coords(42.0), for: "leg-a")

        let retrieved = try XCTUnwrap(cache.coordinates(for: "leg-a"))
        XCTAssertEqual(retrieved.first?.latitude ?? -999, 42.0, accuracy: 0.0001)
    }

    /// Req 11 "cache does not require MapKit UI objects": bu test yalnızca
    /// `CoreLocation` import ediyor, `MapKit` DEĞİL — saklanan tek şey düz
    /// bir değer tipi (`[CLLocationCoordinate2D]`), `MKRoute`/`MKPolyline`/
    /// `MKMapView` değil (bunları taklit etmek zaten mümkün değil, bkz.
    /// `OptimizerRoutingProviding` doc yorumu). `OptimizerRouteCache.swift`
    /// dosyasının kendisi de hiç `import MapKit` içermiyor — yapısal
    /// garanti, çalışma zamanı testi değil.
    func test_cache_storesOnlyPlainCoordinates_noMapKitObjectRequired() throws {
        let cache = OptimizerRouteCache()
        let route = [
            CLLocationCoordinate2D(latitude: 41.00, longitude: 29.00),
            CLLocationCoordinate2D(latitude: 41.01, longitude: 29.01),
        ]

        cache.store(route, for: "leg-a")

        let retrieved = try XCTUnwrap(cache.coordinates(for: "leg-a"))
        XCTAssertEqual(retrieved.count, 2)
        XCTAssertEqual(retrieved[0].latitude, 41.00, accuracy: 0.0001)
    }

    // MARK: - Bounded (Req 11 "do not create an unbounded cache")

    func test_capacityExceeded_evictsLeastRecentlyUsedEntry() {
        let cache = OptimizerRouteCache(capacity: 2)
        cache.store(coords(1), for: "a")
        cache.store(coords(2), for: "b")
        cache.store(coords(3), for: "c")   // "a" en eski — atılmalı

        XCTAssertNil(cache.coordinates(for: "a"))
        XCTAssertNotNil(cache.coordinates(for: "b"))
        XCTAssertNotNil(cache.coordinates(for: "c"))
    }

    /// Bir girdi OKUNURSA "en yeni" konuma taşınır — salt YAZMA sırasına
    /// göre değil, GERÇEK LRU (en-az-kullanılan) sırasına göre atılır.
    func test_readingAnEntry_protectsItFromEviction() {
        let cache = OptimizerRouteCache(capacity: 2)
        cache.store(coords(1), for: "a")
        cache.store(coords(2), for: "b")
        _ = cache.coordinates(for: "a")     // "a"yı en-yeni yap
        cache.store(coords(3), for: "c")    // şimdi "b" en eski — atılmalı

        XCTAssertNotNil(cache.coordinates(for: "a"))
        XCTAssertNil(cache.coordinates(for: "b"))
        XCTAssertNotNil(cache.coordinates(for: "c"))
    }
}
