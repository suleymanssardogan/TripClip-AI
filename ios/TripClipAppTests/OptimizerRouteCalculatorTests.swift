import XCTest
import CoreLocation
@testable import TripClipApp

/// `OptimizerRouteCalculator` — MKDirections'ın kendisini test etmiyoruz
/// (`MKRoute`'un public initializer'ı yok, bkz. `OptimizerRoutingProviding`
/// doc yorumu); onun yerine bu protokol soyutlamasının arkasındaki
/// orkestrasyon mantığını (istek inşası, gün ayrımı, önbellek, iptal,
/// stale-yanıt koruması) `FakeOptimizerRoutingProvider`'a karşı test
/// ediyoruz — bkz. docs/ios-trip-optimizer.md "MapKit Directions mimarisi".
@MainActor
final class OptimizerRouteCalculatorTests: XCTestCase {

    private func stop(id: String, day: Int, order: Int, lat: Double, lng: Double) -> OptimizerMapStop {
        OptimizerMapStop(id: id, dayIndex: day, orderIndex: order, name: "Durak \(id)", latitude: lat, longitude: lng)
    }

    // MARK: - Cache key

    func test_cacheKey_isStable_forSameDayAndStops() {
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0),
            stop(id: "b", day: 0, order: 1, lat: 41.1, lng: 29.1),
        ])

        XCTAssertEqual(OptimizerRouteCalculator.cacheKey(for: day), OptimizerRouteCalculator.cacheKey(for: day))
    }

    func test_cacheKey_differsForDifferentDayIndex() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let day0 = OptimizerMapDay(dayIndex: 0, stops: stops)
        let day1 = OptimizerMapDay(dayIndex: 1, stops: stops)

        XCTAssertNotEqual(OptimizerRouteCalculator.cacheKey(for: day0), OptimizerRouteCalculator.cacheKey(for: day1))
    }

    func test_cacheKey_differsForDifferentStopOrder() {
        let a = stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)
        let b = stop(id: "b", day: 0, order: 1, lat: 41.1, lng: 29.1)
        let forward  = OptimizerMapDay(dayIndex: 0, stops: [a, b])
        let reversed = OptimizerMapDay(dayIndex: 0, stops: [b, a])

        XCTAssertNotEqual(
            OptimizerRouteCalculator.cacheKey(for: forward),
            OptimizerRouteCalculator.cacheKey(for: reversed)
        )
    }

    // MARK: - Single-stop day

    func test_load_singleStopDay_producesNoSegments_neverCallsProvider() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)])

        calculator.load(day: day)
        await Task.yield()

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertEqual(calculator.routes[0]?.segments.isEmpty, true)
        XCTAssertEqual(calculator.routes[0]?.isLoading, false)
    }

    // MARK: - Multi-stop day: request construction + ordering

    func test_load_multiStopDay_requestsOneSegmentPerConsecutivePair_inOrder() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
            stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02),
        ])

        calculator.load(day: day)
        await waitUntil { fake.callCount == 2 }

        XCTAssertEqual(fake.callCount, 2)
        XCTAssertEqual(fake.calls[0].from.latitude, 41.00, accuracy: 0.0001)
        XCTAssertEqual(fake.calls[0].to.latitude,   41.01, accuracy: 0.0001)
        XCTAssertEqual(fake.calls[1].from.latitude, 41.01, accuracy: 0.0001)
        XCTAssertEqual(fake.calls[1].to.latitude,   41.02, accuracy: 0.0001)
    }

    // MARK: - Day separation

    func test_load_twoDays_neverRequestsAcrossDayBoundary() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day0 = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])
        let day1 = OptimizerMapDay(dayIndex: 1, stops: [
            stop(id: "c", day: 1, order: 0, lat: 50.00, lng: 10.00),
            stop(id: "d", day: 1, order: 1, lat: 50.01, lng: 10.01),
        ])

        calculator.load(day: day0)
        calculator.load(day: day1)
        await waitUntil { fake.callCount == 2 }

        // Yalnızca kendi günü içindeki iki bacak istendi — day0'ın son
        // durağı (b) ile day1'in ilk durağı (c) arasında ASLA bir istek
        // yapılmadı (Req 2).
        XCTAssertEqual(fake.callCount, 2)
        let crossDayCall = fake.calls.first { call in
            (call.from.latitude == 41.01 && call.to.latitude == 50.00) ||
            (call.from.latitude == 50.00 && call.to.latitude == 41.01)
        }
        XCTAssertNil(crossDayCall, "Day 0 -> Day 1 sınırını geçen bir rota isteği yapılmamalı")
    }

    // MARK: - Success: real route geometry

    func test_load_success_marksSegmentAsRoaded_withProviderCoordinates() async {
        let fake = FakeOptimizerRoutingProvider()
        let curvedPath = [
            CLLocationCoordinate2D(latitude: 41.00, longitude: 29.00),
            CLLocationCoordinate2D(latitude: 41.005, longitude: 29.006),
            CLLocationCoordinate2D(latitude: 41.01, longitude: 29.01),
        ]
        fake.resultProvider = { _, _ in .success(curvedPath) }
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let segments = calculator.routes[0]?.segments ?? []
        XCTAssertEqual(segments.count, 1)
        XCTAssertEqual(segments.first?.isRoaded, true)
        XCTAssertEqual(segments.first?.coordinates.count, 3)
    }

    // MARK: - Failure: graceful straight-line fallback

    func test_load_failure_fallsBackToStraightLineSegment_doesNotCrash() async throws {
        let fake = FakeOptimizerRoutingProvider()
        fake.resultProvider = { _, _ in .failure(FakeRoutingError.simulatedFailure) }
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let segment = try XCTUnwrap(calculator.routes[0]?.segments.first)
        XCTAssertEqual(segment.isRoaded, false)
        XCTAssertEqual(segment.coordinates.count, 2)
        XCTAssertEqual(segment.coordinates.first?.latitude ?? -999, 41.00, accuracy: 0.0001)
        XCTAssertEqual(segment.coordinates.last?.latitude  ?? -999, 41.01, accuracy: 0.0001)
    }

    /// Bir günün ortasındaki bacak başarısız olsa bile diğer bacaklar
    /// hesaplanmaya devam eder — kısmi rota (Req 7 "partial routes should
    /// degrade gracefully").
    func test_load_partialFailure_otherSegmentsStillSucceed() async {
        let fake = FakeOptimizerRoutingProvider()
        fake.resultProvider = { from, to in
            from.latitude == 41.01 ? .failure(FakeRoutingError.simulatedFailure) : .success([from, to])
        }
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
            stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02),
        ])

        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let segments = calculator.routes[0]?.segments ?? []
        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments[0].isRoaded, true)   // a -> b başarılı
        XCTAssertEqual(segments[1].isRoaded, false)  // b -> c başarısız, düz çizgi
    }

    // MARK: - Caching: no duplicate requests

    func test_load_calledTwiceForSameDay_secondCallUsesCache_noNewRequests() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        let countAfterFirst = fake.callCount

        calculator.load(day: day)
        await Task.yield()

        XCTAssertEqual(fake.callCount, countAfterFirst, "Aynı gün+sıralama için ikinci load() yeni istek yapmamalı")
    }

    /// SwiftUI'nin tekrarlayan `body` değerlendirmeleri `load()`'ı aynı gün
    /// için art arda tetikleyebilir — devam eden isteği iptal edip yeniden
    /// BAŞLATMAMALI (Req 5/6/9), aksi halde istek asla tamamlanmaz.
    func test_load_calledRepeatedlyWhileInFlight_doesNotRestartOrDuplicate() async {
        let fake = FakeOptimizerRoutingProvider()
        let gate = AsyncGate()
        fake.gate = gate
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { fake.callCount == 1 }

        // "SwiftUI yeniden render" simülasyonu: aynı gün için tekrar tekrar çağır.
        calculator.load(day: day)
        calculator.load(day: day)
        calculator.load(day: day)
        await Task.yield()

        XCTAssertEqual(fake.callCount, 1, "İn-flight istek tekrar tetiklenince yeniden başlatılmamalı")

        await gate.open()
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1, "Serbest bırakıldıktan sonra da toplam istek sayısı 1 kalmalı")
    }

    // MARK: - Day switching: no cross-contamination

    func test_daySwitching_bothDaysEndUpWithCorrectIndependentRoutes() async throws {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day0 = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])
        let day1 = OptimizerMapDay(dayIndex: 1, stops: [
            stop(id: "c", day: 1, order: 0, lat: 50.00, lng: 10.00),
            stop(id: "d", day: 1, order: 1, lat: 50.01, lng: 10.01),
        ])

        // Kullanıcı "1. Gün"e bakıyor.
        calculator.load(day: day0)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        // Kullanıcı "2. Gün"e geçiyor.
        calculator.load(day: day1)
        await waitUntil { calculator.routes[1]?.isLoading == false }

        // Day 1'in yanıtı Day 0'ın hâlâ ekranda görüntülenen durumunu
        // EZMEMİŞ olmalı (Req 5).
        let day0Segment = try XCTUnwrap(calculator.routes[0]?.segments.first)
        let day1Segment = try XCTUnwrap(calculator.routes[1]?.segments.first)
        XCTAssertEqual(day0Segment.coordinates.first?.latitude ?? -999, 41.00, accuracy: 0.0001)
        XCTAssertEqual(day1Segment.coordinates.first?.latitude ?? -999, 50.00, accuracy: 0.0001)
    }

    // MARK: - Non-contiguous order index (missing-coordinate stop already filtered upstream)

    func test_load_nonContiguousOrderIndex_stillRequestsConsecutivePairsOverSurvivingStops() async {
        // OptimizerRouteMapData zaten koordinatsız durakları eleyip
        // orderIndex'te boşluk bırakabiliyor (bkz. OptimizerRouteMapDataTests) —
        // calculator bu diziyi olduğu gibi, ardışık ikili olarak işlemeli.
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02),  // orderIndex 1 (koordinatsız) atlanmış
        ])

        calculator.load(day: day)
        await waitUntil { fake.callCount == 1 }

        XCTAssertEqual(fake.callCount, 1)
        XCTAssertEqual(fake.calls[0].from.latitude, 41.00, accuracy: 0.0001)
        XCTAssertEqual(fake.calls[0].to.latitude,   41.02, accuracy: 0.0001)
    }

    // MARK: - Cancellation

    func test_cancelAll_doesNotCrash_andAllowsFreshLoadAfterward() async {
        let fake = FakeOptimizerRoutingProvider()
        let gate = AsyncGate()
        fake.gate = gate
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { fake.callCount == 1 }

        calculator.cancelAll()
        await gate.open()   // eski (iptal edilmiş) isteğin askıda kalan continuation'ını serbest bırak
        await Task.yield()

        // Aynı calculator üzerinde yeniden yüklemek çalışmaya devam
        // etmeli — iptal, kalıcı olarak bozulmuş bir state bırakmamalı
        // (in-flight takip dictionary'leri `cancelAll` içinde temizleniyor).
        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 2, "İptalden sonraki yeniden yükleme yeni bir istek yapmalı")
    }

    // MARK: - Test helper

    /// Basit bir "koşul gerçek olana kadar bekle" yardımcı — asenkron
    /// state'in ne zaman yerleştiğini `Task.yield()` sayısına güvenerek
    /// tahmin etmek yerine.
    private func waitUntil(
        timeout: TimeInterval = 2, _ condition: @escaping () -> Bool
    ) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition() && Date() < deadline {
            await Task.yield()
            try? await Task.sleep(nanoseconds: 1_000_000)
        }
    }
}
