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

    // MARK: - Persistent Optimizer Route Cache — cacheKey itinerary isolation

    /// Req 4/15: itinerary kimliği olmadan "Itinerary A + Day 1" ile
    /// "Itinerary B + Day 1" aynı gün+durak diziliminde olduklarında AYNI
    /// anahtarı üretirdi — bu test bunun artık mümkün olmadığını doğruluyor.
    func test_cacheKey_differsForDifferentItineraryID_evenWithIdenticalDayAndStops() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let dayInItineraryA = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stops)
        let dayInItineraryB = OptimizerMapDay(dayIndex: 0, itineraryID: 2, stops: stops)

        XCTAssertNotEqual(
            OptimizerRouteCalculator.cacheKey(for: dayInItineraryA),
            OptimizerRouteCalculator.cacheKey(for: dayInItineraryB)
        )
    }

    // MARK: - Persistent Optimizer Route Cache — survives calculator/screen recreation

    /// Req 6/7/10/13/17'nin merkezi senaryosu: "History → open saved
    /// itinerary → route calculation → leave screen → reopen same saved
    /// itinerary → route should come from cache." İKİ AYRI
    /// `OptimizerRouteCalculator` (birinci ekran ziyareti / ikinci ekran
    /// ziyareti — her `TripOptimizerView` push'unda `@State` yeniden
    /// kurulur) aynı `OptimizerRouteCache`'i PAYLAŞIYOR — bu, üretim
    /// kodundaki `OptimizerRouteMapSection.init`'in enjekte ettiği paylaşılan
    /// önbelleğin AYNISI (bkz. `TripClipApp.swift`).
    func test_persistentCache_survivesCalculatorRecreation_secondVisitReusesResult_noNewRequest() async {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 7, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        // Birinci ekran ziyareti: gerçek bir istek yapılmalı.
        let firstVisitProvider = FakeOptimizerRoutingProvider()
        let firstVisitCalculator = OptimizerRouteCalculator(provider: firstVisitProvider, cache: sharedCache)
        firstVisitCalculator.load(day: day)
        await waitUntil { firstVisitCalculator.routes[0]?.isLoading == false }
        XCTAssertEqual(firstVisitProvider.callCount, 1, "İlk ziyaret rota sağlayıcısını çağırmalı")

        // Ekrandan çıkılıp AYNI itinerary tekrar açıldığında (Req 10: yeni
        // bir OptimizerRouteCalculator örneği — `OptimizerRouteMapSection`'ın
        // `@State`'i yeniden kurulur) — paylaşılan önbellek sayesinde ikinci
        // ziyaret HİÇBİR yeni istek yapmamalı (Req 17).
        let secondVisitProvider = FakeOptimizerRoutingProvider()
        let secondVisitCalculator = OptimizerRouteCalculator(provider: secondVisitProvider, cache: sharedCache)
        secondVisitCalculator.load(day: day)

        // Req 16: senkron — hiçbir "loading" ANI bile yaşanmaz.
        XCTAssertEqual(secondVisitCalculator.routes[0]?.isLoading, false)
        XCTAssertEqual(secondVisitCalculator.routes[0]?.segments.count, 1)
        XCTAssertEqual(secondVisitCalculator.routes[0]?.segments.first?.isRoaded, true)
        XCTAssertEqual(secondVisitProvider.callCount, 0, "İkinci ziyaret HİÇ yeni istek yapmamalı")
    }

    // MARK: - Persistent Optimizer Route Cache — itinerary isolation

    /// Req 4: "Itinerary A + Day 1 ≠ Itinerary B + Day 1 even if both
    /// contain the same number of stops." Aynı paylaşılan önbellek, iki
    /// FARKLI itinerary'nin aynı gün+durak şekli için bile birbirinin
    /// sonucunu asla ödünç vermemeli.
    func test_persistentCache_differentItinerary_sameShapedDay_doesNotReuseCachedResult() async {
        let sharedCache = OptimizerRouteCache()
        let stopsShape: [OptimizerMapStop] = [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ]
        let dayInItineraryA = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stopsShape)
        let dayInItineraryB = OptimizerMapDay(dayIndex: 0, itineraryID: 2, stops: stopsShape)

        let providerA = FakeOptimizerRoutingProvider()
        let calculatorA = OptimizerRouteCalculator(provider: providerA, cache: sharedCache)
        calculatorA.load(day: dayInItineraryA)
        await waitUntil { calculatorA.routes[0]?.isLoading == false }
        XCTAssertEqual(providerA.callCount, 1)

        let providerB = FakeOptimizerRoutingProvider()
        let calculatorB = OptimizerRouteCalculator(provider: providerB, cache: sharedCache)
        calculatorB.load(day: dayInItineraryB)
        await waitUntil { calculatorB.routes[0]?.isLoading == false }
        XCTAssertEqual(providerB.callCount, 1, "Farklı itinerary aynı gün-şekli olsa bile önbelleği paylaşmamalı")
    }

    // MARK: - Persistent Optimizer Route Cache — day isolation

    /// Req 4/13 "different day does not reuse cached result" — aynı
    /// itinerary içinde bile, farklı bir `dayIndex` önbellek isabetine yol
    /// açmamalı (durak şekli aynı olsa bile — teorik bir kenar durum, ama
    /// `legKey`'in `dayIndex`'i gerçekten içerdiğini doğrudan kanıtlıyor).
    func test_persistentCache_differentDayIndex_sameItinerary_doesNotReuseCachedResult() async {
        let sharedCache = OptimizerRouteCache()
        let stopsShape: [OptimizerMapStop] = [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ]
        let day0 = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stopsShape)
        let day1 = OptimizerMapDay(dayIndex: 1, itineraryID: 1, stops: stopsShape)

        let providerDay0 = FakeOptimizerRoutingProvider()
        let calculatorDay0 = OptimizerRouteCalculator(provider: providerDay0, cache: sharedCache)
        calculatorDay0.load(day: day0)
        await waitUntil { calculatorDay0.routes[0]?.isLoading == false }

        let providerDay1 = FakeOptimizerRoutingProvider()
        let calculatorDay1 = OptimizerRouteCalculator(provider: providerDay1, cache: sharedCache)
        calculatorDay1.load(day: day1)
        await waitUntil { calculatorDay1.routes[1]?.isLoading == false }
        XCTAssertEqual(providerDay1.callCount, 1, "Farklı gün indeksi önbelleği paylaşmamalı")
    }

    // MARK: - Persistent Optimizer Route Cache — stale route protection

    /// Req 5/13 "changed stop order invalidates cache" — durak SIRASI
    /// değişince bacaklar (from→to çiftleri) da değiştiğinden, eski sıranın
    /// önbelleği yeni sıra için asla yanlışlıkla kullanılmamalı.
    func test_persistentCache_changedStopOrder_invalidatesCache() async {
        let sharedCache = OptimizerRouteCache()
        let a = stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00)
        let b = stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01)
        let c = stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02)

        let originalOrder = OptimizerMapDay(dayIndex: 0, itineraryID: 5, stops: [a, b, c])
        let provider1 = FakeOptimizerRoutingProvider()
        let calculator1 = OptimizerRouteCalculator(provider: provider1, cache: sharedCache)
        calculator1.load(day: originalOrder)
        await waitUntil { calculator1.routes[0]?.isLoading == false }
        XCTAssertEqual(provider1.callCount, 2, "a→b ve b→c için iki bacak")

        let reorderedStops = OptimizerMapDay(dayIndex: 0, itineraryID: 5, stops: [b, a, c])
        let provider2 = FakeOptimizerRoutingProvider()
        let calculator2 = OptimizerRouteCalculator(provider: provider2, cache: sharedCache)
        calculator2.load(day: reorderedStops)
        await waitUntil { calculator2.routes[0]?.isLoading == false }
        XCTAssertEqual(
            provider2.callCount, 2,
            "Yeniden sıralanmış bacaklar (b→a, a→c) önbellekte YOK — ikisi de yeniden istenmeli"
        )
    }

    /// Req 5/13 "changed coordinates invalidate cache" — bir durağın
    /// koordinatı değişirse (aynı `id` kalsa bile) o bacağın önbelleği
    /// geçersiz sayılmalı, çünkü artık farklı bir fiziksel rota demektir.
    func test_persistentCache_changedCoordinates_invalidatesCache() async {
        let sharedCache = OptimizerRouteCache()
        let a = stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00)
        let bOriginal = stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01)
        let bMoved    = stop(id: "b", day: 0, order: 1, lat: 42.50, lng: 30.50)

        let day1 = OptimizerMapDay(dayIndex: 0, itineraryID: 5, stops: [a, bOriginal])
        let provider1 = FakeOptimizerRoutingProvider()
        let calculator1 = OptimizerRouteCalculator(provider: provider1, cache: sharedCache)
        calculator1.load(day: day1)
        await waitUntil { calculator1.routes[0]?.isLoading == false }

        let day2 = OptimizerMapDay(dayIndex: 0, itineraryID: 5, stops: [a, bMoved])
        let provider2 = FakeOptimizerRoutingProvider()
        let calculator2 = OptimizerRouteCalculator(provider: provider2, cache: sharedCache)
        calculator2.load(day: day2)
        await waitUntil { calculator2.routes[0]?.isLoading == false }
        XCTAssertEqual(provider2.callCount, 1, "Değişen koordinat önbelleği geçersiz kılmalı")
    }

    // MARK: - Persistent Optimizer Route Cache — failure semantics (Req 8/9)

    /// Req 8: "Do NOT cache failed route calculations... a later visit may
    /// retry the failed route." Başarısız bir bacak kalıcı önbelleğe hiç
    /// girmemeli — bir sonraki ekran ziyareti onu yeniden denemeli, ve bu
    /// sefer başarılıysa gerçek rota geometrisiyle sonuçlanmalı.
    func test_persistentCache_failedResult_isNotCached_retriedOnNextVisit() async throws {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 9, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        let failingProvider = FakeOptimizerRoutingProvider()
        failingProvider.resultProvider = { _, _ in .failure(FakeRoutingError.simulatedFailure) }
        let firstVisit = OptimizerRouteCalculator(provider: failingProvider, cache: sharedCache)
        firstVisit.load(day: day)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        XCTAssertEqual(firstVisit.routes[0]?.segments.first?.isRoaded, false)

        let succeedingProvider = FakeOptimizerRoutingProvider()   // varsayılan: başarılı
        let secondVisit = OptimizerRouteCalculator(provider: succeedingProvider, cache: sharedCache)
        secondVisit.load(day: day)
        await waitUntil { secondVisit.routes[0]?.isLoading == false }

        XCTAssertEqual(succeedingProvider.callCount, 1, "Başarısız bacak önbelleğe alınmadıysa yeniden denenmeli")
        let segment = try XCTUnwrap(secondVisit.routes[0]?.segments.first)
        XCTAssertEqual(segment.isRoaded, true, "İkinci ziyarette başarılı olan bacak artık gerçek rota")
    }

    /// Req 9: "successful legs may be cached; failed legs must remain
    /// retryable; do not cache an entire day as successful when individual
    /// route segments failed." Üç duraklı bir günde bir bacak başarısız
    /// olsa bile DİĞER (başarılı) bacak önbelleğe alınmalı — bir sonraki
    /// ziyarette yalnızca başarısız kalan bacak yeniden istenmeli.
    func test_persistentCache_partialFailure_onlySuccessfulLegCached_nextVisitRetriesOnlyFailedLeg() async throws {
        let sharedCache = OptimizerRouteCache()
        let a = stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00)
        let b = stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01)
        let c = stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02)
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 11, stops: [a, b, c])

        let firstProvider = FakeOptimizerRoutingProvider()
        firstProvider.resultProvider = { from, to in
            from.latitude == 41.01 ? .failure(FakeRoutingError.simulatedFailure) : .success([from, to])
        }
        let firstVisit = OptimizerRouteCalculator(provider: firstProvider, cache: sharedCache)
        firstVisit.load(day: day)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        XCTAssertEqual(firstProvider.callCount, 2, "a→b ve b→c için iki istek")

        let secondProvider = FakeOptimizerRoutingProvider()   // varsayılan: başarılı
        let secondVisit = OptimizerRouteCalculator(provider: secondProvider, cache: sharedCache)
        secondVisit.load(day: day)
        await waitUntil { secondVisit.routes[0]?.isLoading == false }

        XCTAssertEqual(
            secondProvider.callCount, 1,
            "Yalnızca daha önce BAŞARISIZ olan b→c bacağı yeniden istenmeli — a→b önbellekten gelmeli"
        )
        let segments = try XCTUnwrap(secondVisit.routes[0]?.segments)
        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments[0].isRoaded, true, "a→b önbellekten (zaten başarılıydı)")
        XCTAssertEqual(segments[1].isRoaded, true, "b→c bu ziyarette başarıyla yeniden hesaplandı")
    }

    // MARK: - Persistent Optimizer Route Cache — in-flight de-duplication preserved

    /// Req 10: paylaşılan bir önbellek enjekte edilmiş olsa bile, aynı
    /// calculator örneğinde devam eden bir isteğin tekrar tetiklenmemesi
    /// davranışı BOZULMAMALI (bkz. `test_load_calledRepeatedlyWhileInFlight_doesNotRestartOrDuplicate`
    /// — o test varsayılan/özel önbellek ayrımı yapmadan zaten bunu
    /// kapsıyor; bu test aynı senaryoyu AÇIKÇA enjekte edilmiş paylaşılan
    /// bir önbellekle tekrarlayarak ikisinin etkileşmediğini doğruluyor).
    func test_persistentCache_inFlightDeduplication_stillPreventsRestart_withInjectedCache() async {
        let sharedCache = OptimizerRouteCache()
        let fake = FakeOptimizerRoutingProvider()
        let gate = AsyncGate()
        fake.gate = gate
        let calculator = OptimizerRouteCalculator(provider: fake, cache: sharedCache)
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 3, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { fake.callCount == 1 }

        calculator.load(day: day)
        calculator.load(day: day)
        await Task.yield()
        XCTAssertEqual(fake.callCount, 1, "In-flight isteğe rağmen tekrar çağrı yapılmamalı")

        await gate.open()
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1)
    }

    // MARK: - Optimizer Route Transport Mode — cache key

    /// Aynı `legKey`/`cacheKey` mantığının Req 4 (Persistent Optimizer
    /// Route Cache) için `itineraryID`'yi eklediği gibi, bu milestone de
    /// `mode`'u eklemeli — aksi halde Araba ile Yürüyüş aynı gün+durak
    /// dizilimi için AYNI yapısal kimliği paylaşır ve biri diğerinin
    /// önbelleğini yanlışlıkla ödünç alır.
    func test_cacheKey_differsForDifferentMode_evenWithIdenticalDayAndStops() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stops)

        XCTAssertNotEqual(
            OptimizerRouteCalculator.cacheKey(for: day, mode: .automobile),
            OptimizerRouteCalculator.cacheKey(for: day, mode: .walking)
        )
    }

    /// `mode` parametresiz eski çağıranlar (bu dosyanın kendi önceki
    /// testleri dahil) Req 12'nin istediği gibi `.automobile`'a
    /// varsayılanlı kalmalı — yani mod belirtmeden üretilen bir anahtar,
    /// açıkça `.automobile` belirtilerek üretilenle AYNI olmalı.
    func test_cacheKey_omittingMode_defaultsToAutomobile() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stops)

        XCTAssertEqual(
            OptimizerRouteCalculator.cacheKey(for: day),
            OptimizerRouteCalculator.cacheKey(for: day, mode: .automobile)
        )
    }

    // MARK: - Optimizer Route Transport Mode — mode reaches the provider

    /// `load(day:)` mod belirtmeden çağrılırsa (mevcut, milestone-öncesi
    /// çağrı biçimi) sağlayıcıya ulaşan mod `.automobile` olmalı — Req 12
    /// "existing callers should continue to default to automobile".
    func test_load_omittingMode_reachesProviderAsAutomobile() async throws {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let call = try XCTUnwrap(fake.calls.first)
        XCTAssertEqual(call.mode, .automobile)
    }

    /// `load(day:mode:)`'a `.walking` verildiğinde, sağlayıcıya ulaşan
    /// istekteki mod gerçekten `.walking` olmalı (Req 7: "automobile →
    /// .automobile, walking → .walking are actually being requested").
    func test_load_walkingMode_reachesProviderAsWalking() async throws {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let call = try XCTUnwrap(fake.calls.first)
        XCTAssertEqual(call.mode, .walking)
    }

    // MARK: - Optimizer Route Transport Mode — switching modes / lifecycle

    /// Aynı gün, mod değişir değişmez o günün EKRANDA GÖSTERİLEN rotası
    /// hemen temizlenip yeniden "loading" durumuna dönmeli — eski modun
    /// rotası asılı KALMAMALI (Req 5 "clear displayed route for current
    /// day, then calculate the route for the new mode"). `AsyncGate` ile
    /// ikinci (yürüyüş) isteğini askıda tutup ARA durumu doğrudan
    /// gözlemliyoruz.
    func test_switchingMode_immediatelyClearsPreviousModesRoute_showsLoadingForNewMode() async throws {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .automobile)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(calculator.routes[0]?.segments.first?.isRoaded, true)

        let gate = AsyncGate()
        fake.gate = gate
        calculator.load(day: day, mode: .walking)

        // Yeni istek başladı ama henüz tamamlanmadı — gösterilen rota HEMEN
        // düz-çizgi + loading'e dönmüş olmalı, eski (automobile) rotalı
        // segment ekranda ASILI KALMAMALI.
        await waitUntil { fake.callCount == 2 }
        XCTAssertEqual(calculator.routes[0]?.isLoading, true)
        XCTAssertEqual(calculator.routes[0]?.segments.first?.isRoaded, false)

        await gate.open()
        await waitUntil { calculator.routes[0]?.isLoading == false }
        let call = try XCTUnwrap(fake.calls.last)
        XCTAssertEqual(call.mode, .walking)
    }

    /// Req: "select another stop in same day must NOT restart routing" —
    /// mod SABİT kalırken tekrar `load` çağırmak (bir durak seçiminin
    /// `OptimizerRouteMapSection`'da tetiklediği gibi) yeni bir istek
    /// BAŞLATMAMALI, aynı kalıcı-önbellek/in-flight korumasından geçmeli.
    func test_repeatedLoad_sameMode_doesNotRestartRouting() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        let countAfterFirst = fake.callCount

        calculator.load(day: day, mode: .walking)
        await Task.yield()

        XCTAssertEqual(fake.callCount, countAfterFirst, "Aynı mod için tekrar load() yeni istek yapmamalı")
    }

    /// Req: "switch to another day must continue respecting the existing
    /// day cache/in-flight behavior" — gün değişimi, taşıma modu ne olursa
    /// olsun, her günün kendi bağımsız önbellek/in-flight durumunu korumalı.
    func test_daySwitching_remainsIsolated_regardlessOfTransportMode() async throws {
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

        calculator.load(day: day0, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        calculator.load(day: day1, mode: .walking)
        await waitUntil { calculator.routes[1]?.isLoading == false }

        XCTAssertEqual(fake.callCount, 2, "İki gün için iki bağımsız bacak isteği")
        let day0Segment = try XCTUnwrap(calculator.routes[0]?.segments.first)
        let day1Segment = try XCTUnwrap(calculator.routes[1]?.segments.first)
        XCTAssertEqual(day0Segment.coordinates.first?.latitude ?? -999, 41.00, accuracy: 0.0001)
        XCTAssertEqual(day1Segment.coordinates.first?.latitude ?? -999, 50.00, accuracy: 0.0001)
    }

    /// Kısmi başarısızlık (Req 9'un genel semantiği) yürüyüş modu için de
    /// AYNEN geçerli olmalı — bu bir davranış REGRESYONU değil.
    func test_partialFailure_stillWorksForWalkingMode() async throws {
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

        calculator.load(day: day, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let segments = calculator.routes[0]?.segments ?? []
        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments[0].isRoaded, true)
        XCTAssertEqual(segments[1].isRoaded, false)
        XCTAssertTrue(fake.calls.allSatisfy { $0.mode == .walking }, "Her iki bacak isteği de yürüyüş modunda olmalı")
    }

    /// `cancelAll()` + yeniden yükleme davranışı taşıma modundan bağımsız
    /// olmalı — v11'in kendi `test_cancelAll_doesNotCrash_andAllowsFreshLoadAfterward`
    /// testinin AYNISI, ama açıkça `.walking` ile.
    func test_cancelAll_stillWorksWithNonDefaultTransportMode() async {
        let fake = FakeOptimizerRoutingProvider()
        let gate = AsyncGate()
        fake.gate = gate
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .walking)
        await waitUntil { fake.callCount == 1 }

        calculator.cancelAll()
        await gate.open()
        await Task.yield()

        calculator.load(day: day, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 2, "İptalden sonraki yeniden yükleme yeni bir istek yapmalı")
    }

    // MARK: - Optimizer Route Transport Mode — cache correctness (CRITICAL)

    /// Req 4'ün tam senaryosu: sürüş → tekrar sürüş (önbellekten) → yürüyüşe
    /// geç (yeni istek) → tekrar yürüyüş (önbellekten) → sürüşe dön (ORİJİNAL
    /// sürüş sonucu önbellekten, yeni istek YOK). Tek bir akan test, aynı
    /// calculator/aynı sağlayıcı üzerinde `fake.callCount`'un her adımda
    /// beklenen şekilde değiştiğini/değişmediğini doğruluyor.
    func test_transportModeCache_drivingThenWalkingThenBackToDriving_eachModeIndependentlyCached() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        // 1. Sürüş isteği normal şekilde önbelleğe alınır.
        calculator.load(day: day, mode: .automobile)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1)

        // 2. Sürüşü TEKRARLAMAK önbellekten gelir — yeni istek YOK.
        calculator.load(day: day, mode: .automobile)
        XCTAssertEqual(calculator.routes[0]?.isLoading, false, "Önbellek isabeti SENKRON olmalı")
        XCTAssertEqual(fake.callCount, 1)

        // 3. Yürüyüşe GEÇMEK yeni bir istek başlatır.
        calculator.load(day: day, mode: .walking)
        await waitUntil { fake.callCount == 2 }
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 2)

        // 4. Yürüyüşü TEKRARLAMAK yürüyüş önbelleğinden gelir — yeni istek YOK.
        calculator.load(day: day, mode: .walking)
        XCTAssertEqual(calculator.routes[0]?.isLoading, false)
        XCTAssertEqual(fake.callCount, 2)

        // 5. Sürüşe GERİ DÖNMEK orijinal sürüş sonucunu önbellekten getirir
        //    — yeni istek YOK (adım 1'de zaten önbelleğe alınmıştı).
        calculator.load(day: day, mode: .automobile)
        XCTAssertEqual(calculator.routes[0]?.isLoading, false, "Sürüşe dönüş SENKRON/önbellekten olmalı")
        XCTAssertEqual(fake.callCount, 2, "Sürüşe dönüş yeni istek yapmamalı")
    }

    /// Req 6: "different transport modes can coexist in the same
    /// OptimizerRouteCache." Sürüş VE yürüyüş bir kez hesaplandıktan sonra,
    /// TAMAMEN YENİ (ekran yeniden açılmışçasına) bir calculator aynı
    /// paylaşılan önbelleği kullanarak HER İKİ modu da yeni istek yapmadan
    /// bulabilmeli.
    func test_transportModeCache_bothModesCoexist_inSameSharedCache() async {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 2, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        let firstVisitProvider = FakeOptimizerRoutingProvider()
        let firstVisit = OptimizerRouteCalculator(provider: firstVisitProvider, cache: sharedCache)
        firstVisit.load(day: day, mode: .automobile)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        firstVisit.load(day: day, mode: .walking)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        XCTAssertEqual(firstVisitProvider.callCount, 2, "Bir sürüş, bir yürüyüş isteği")

        let secondVisitProvider = FakeOptimizerRoutingProvider()
        let secondVisit = OptimizerRouteCalculator(provider: secondVisitProvider, cache: sharedCache)

        secondVisit.load(day: day, mode: .automobile)
        XCTAssertEqual(secondVisit.routes[0]?.isLoading, false)
        XCTAssertEqual(secondVisit.routes[0]?.segments.first?.isRoaded, true)

        secondVisit.load(day: day, mode: .walking)
        XCTAssertEqual(secondVisit.routes[0]?.isLoading, false)
        XCTAssertEqual(secondVisit.routes[0]?.segments.first?.isRoaded, true)

        XCTAssertEqual(secondVisitProvider.callCount, 0, "İki mod da önbellekten gelmeli — hiç yeni istek yok")
    }

    /// Req: "existing structural invalidation still works" — durak sırası
    /// değişimi, mod önbellek kimliğine eklendikten SONRA da geçerliliğini
    /// korumalı (v11'in `test_persistentCache_changedStopOrder_invalidatesCache`
    /// testinin AYNISı, ama açıkça yürüyüş modunda).
    func test_transportModeCache_structuralInvalidation_stopOrderChange_stillInvalidatesCache() async {
        let sharedCache = OptimizerRouteCache()
        let a = stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00)
        let b = stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01)
        let c = stop(id: "c", day: 0, order: 2, lat: 41.02, lng: 29.02)

        let originalOrder = OptimizerMapDay(dayIndex: 0, itineraryID: 6, stops: [a, b, c])
        let provider1 = FakeOptimizerRoutingProvider()
        let calculator1 = OptimizerRouteCalculator(provider: provider1, cache: sharedCache)
        calculator1.load(day: originalOrder, mode: .walking)
        await waitUntil { calculator1.routes[0]?.isLoading == false }
        XCTAssertEqual(provider1.callCount, 2)

        let reorderedStops = OptimizerMapDay(dayIndex: 0, itineraryID: 6, stops: [b, a, c])
        let provider2 = FakeOptimizerRoutingProvider()
        let calculator2 = OptimizerRouteCalculator(provider: provider2, cache: sharedCache)
        calculator2.load(day: reorderedStops, mode: .walking)
        await waitUntil { calculator2.routes[0]?.isLoading == false }
        XCTAssertEqual(provider2.callCount, 2, "Yeniden sıralanmış bacaklar aynı modda bile önbellekte yok")
    }

    /// Req: "failed requests are still never cached" — moddan bağımsız,
    /// başarısız bir bacak asla önbelleğe girmemeli.
    func test_transportModeCache_failedRequest_isNeverCached_regardlessOfMode() async throws {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 8, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        let failingProvider = FakeOptimizerRoutingProvider()
        failingProvider.resultProvider = { _, _ in .failure(FakeRoutingError.simulatedFailure) }
        let firstVisit = OptimizerRouteCalculator(provider: failingProvider, cache: sharedCache)
        firstVisit.load(day: day, mode: .walking)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        XCTAssertEqual(firstVisit.routes[0]?.segments.first?.isRoaded, false)

        let succeedingProvider = FakeOptimizerRoutingProvider()
        let secondVisit = OptimizerRouteCalculator(provider: succeedingProvider, cache: sharedCache)
        secondVisit.load(day: day, mode: .walking)
        await waitUntil { secondVisit.routes[0]?.isLoading == false }

        XCTAssertEqual(succeedingProvider.callCount, 1, "Başarısız yürüyüş bacağı önbelleğe alınmadıysa yeniden denenmeli")
        let segment = try XCTUnwrap(secondVisit.routes[0]?.segments.first)
        XCTAssertEqual(segment.isRoaded, true)
    }

    // MARK: - Transit Transport Mode — cache key

    /// Req 9/10: transit'in yapısal önbellek kimliği, hem automobile hem
    /// walking'den AYRI olmalı — aynı `test_cacheKey_differsForDifferentMode_evenWithIdenticalDayAndStops`
    /// mantığı, üçüncü bir mod için.
    func test_cacheKey_transitDiffersFromAutomobile() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stops)

        XCTAssertNotEqual(
            OptimizerRouteCalculator.cacheKey(for: day, mode: .transit),
            OptimizerRouteCalculator.cacheKey(for: day, mode: .automobile)
        )
    }

    func test_cacheKey_transitDiffersFromWalking() {
        let stops = [stop(id: "a", day: 0, order: 0, lat: 41.0, lng: 29.0)]
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 1, stops: stops)

        XCTAssertNotEqual(
            OptimizerRouteCalculator.cacheKey(for: day, mode: .transit),
            OptimizerRouteCalculator.cacheKey(for: day, mode: .walking)
        )
    }

    // MARK: - Transit Transport Mode — mode reaches the provider

    /// Req 8: `load(day:mode: .transit)` sağlayıcıya ulaşan istekte
    /// gerçekten `.transit` göndermeli.
    func test_load_transitMode_reachesProviderAsTransit() async throws {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .transit)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let call = try XCTUnwrap(fake.calls.first)
        XCTAssertEqual(call.mode, .transit)
    }

    // MARK: - Transit Transport Mode — cache correctness (CRITICAL)

    /// Req 11: bir kez hesaplanan transit rotası tekrar `load` çağrısında
    /// önbellekten SENKRON gelir — yeni istek yok.
    func test_transitCache_cachedResultIsReused_noDuplicateRequest() async {
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake)
        let day = OptimizerMapDay(dayIndex: 0, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        calculator.load(day: day, mode: .transit)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1)

        calculator.load(day: day, mode: .transit)
        XCTAssertEqual(calculator.routes[0]?.isLoading, false, "Önbellek isabeti SENKRON olmalı")
        XCTAssertEqual(fake.callCount, 1, "Transit tekrarı yeni istek yapmamalı")
    }

    /// Req 12/4: transit rotası bulunamadığında (bölge/kapsama/zaman
    /// nedeniyle beklenen bir durum, hata değil) crash yok, düz-çizgiye
    /// düşer, ve BAŞARISIZ bacak kalıcı önbelleğe hiç yazılmaz — bir
    /// sonraki ziyarette yeniden denenebilir kalır (Req 4 "allow the next
    /// visit/request to retry").
    func test_transitCache_failedRequest_isNeverCached() async throws {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 9, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        let failingProvider = FakeOptimizerRoutingProvider()
        failingProvider.resultProvider = { _, _ in .failure(FakeRoutingError.simulatedFailure) }
        let firstVisit = OptimizerRouteCalculator(provider: failingProvider, cache: sharedCache)
        firstVisit.load(day: day, mode: .transit)
        await waitUntil { firstVisit.routes[0]?.isLoading == false }
        XCTAssertEqual(firstVisit.routes[0]?.segments.first?.isRoaded, false, "Transit rota bulunamadığında düz-çizgiye düşmeli")

        let succeedingProvider = FakeOptimizerRoutingProvider()
        let secondVisit = OptimizerRouteCalculator(provider: succeedingProvider, cache: sharedCache)
        secondVisit.load(day: day, mode: .transit)
        await waitUntil { secondVisit.routes[0]?.isLoading == false }

        XCTAssertEqual(succeedingProvider.callCount, 1, "Başarısız transit bacağı önbelleğe alınmadıysa yeniden denenmeli")
        let segment = try XCTUnwrap(secondVisit.routes[0]?.segments.first)
        XCTAssertEqual(segment.isRoaded, true)
    }

    /// Req 13: bir günün bazı bacakları transit için bulunamasa bile,
    /// başarılı bacaklar kaybolmaz — kısmi başarısızlık davranışı
    /// (v6'dan beri var olan) transit için de AYNEN geçerli.
    func test_transitPartialFailure_preservesSuccessfulLegs() async throws {
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

        calculator.load(day: day, mode: .transit)
        await waitUntil { calculator.routes[0]?.isLoading == false }

        let segments = calculator.routes[0]?.segments ?? []
        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments[0].isRoaded, true)
        XCTAssertEqual(segments[1].isRoaded, false)
        XCTAssertTrue(fake.calls.allSatisfy { $0.mode == .transit }, "Her iki bacak isteği de transit modunda olmalı")
    }

    /// Req 14: yürüyüşten transit'e geçiş, yürüyüşün önbelleğini ÖDÜNÇ
    /// ALMAMALI — yeni bir istek yapmalı.
    func test_transportModeCache_walkingThenTransit_switchingDoesNotReuseWalkingRoute() async {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 10, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake, cache: sharedCache)

        calculator.load(day: day, mode: .walking)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1)

        calculator.load(day: day, mode: .transit)
        await waitUntil { fake.callCount == 2 }
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 2, "Transit'e geçiş yürüyüş önbelleğini ödünç ALMAMALI, yeni istek yapmalı")
    }

    /// Req 15: transit'ten automobile'a geçiş, transit'in önbelleğini
    /// ÖDÜNÇ ALMAMALI — yeni bir istek yapmalı.
    func test_transportModeCache_transitThenAutomobile_switchingDoesNotReuseTransitRoute() async {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 11, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])
        let fake = FakeOptimizerRoutingProvider()
        let calculator = OptimizerRouteCalculator(provider: fake, cache: sharedCache)

        calculator.load(day: day, mode: .transit)
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 1)

        calculator.load(day: day, mode: .automobile)
        await waitUntil { fake.callCount == 2 }
        await waitUntil { calculator.routes[0]?.isLoading == false }
        XCTAssertEqual(fake.callCount, 2, "Araba'ya geçiş transit önbelleğini ödünç ALMAMALI, yeni istek yapmalı")
    }

    /// Req 6 (milestone spec): "add explicit tests proving transit entries
    /// coexist with automobile and walking entries" — `OptimizerTransportMode.allCases`
    /// üzerinden JENERİK olarak yazıldı, böylece gelecekte bir mod daha
    /// eklenirse bu test otomatik olarak onu da kapsar.
    func test_transportModeCache_allThreeModesCoexist_inSameSharedCache() async {
        let sharedCache = OptimizerRouteCache()
        let day = OptimizerMapDay(dayIndex: 0, itineraryID: 12, stops: [
            stop(id: "a", day: 0, order: 0, lat: 41.00, lng: 29.00),
            stop(id: "b", day: 0, order: 1, lat: 41.01, lng: 29.01),
        ])

        let firstVisitProvider = FakeOptimizerRoutingProvider()
        let firstVisit = OptimizerRouteCalculator(provider: firstVisitProvider, cache: sharedCache)
        for mode in OptimizerTransportMode.allCases {
            firstVisit.load(day: day, mode: mode)
            await waitUntil { firstVisit.routes[0]?.isLoading == false }
        }
        XCTAssertEqual(firstVisitProvider.callCount, OptimizerTransportMode.allCases.count, "Her mod için bir istek")

        let secondVisitProvider = FakeOptimizerRoutingProvider()
        let secondVisit = OptimizerRouteCalculator(provider: secondVisitProvider, cache: sharedCache)
        for mode in OptimizerTransportMode.allCases {
            secondVisit.load(day: day, mode: mode)
            XCTAssertEqual(secondVisit.routes[0]?.isLoading, false)
            XCTAssertEqual(secondVisit.routes[0]?.segments.first?.isRoaded, true)
        }
        XCTAssertEqual(secondVisitProvider.callCount, 0, "Tüm modlar önbellekten gelmeli — hiç yeni istek yok")
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
