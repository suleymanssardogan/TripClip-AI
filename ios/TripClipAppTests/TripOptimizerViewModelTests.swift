import XCTest
@testable import TripClipApp

@MainActor
final class TripOptimizerViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    // MARK: - Initial state

    func test_initialState_isNotLoading_hasNoItinerary_hasNoError() {
        let vm = TripOptimizerViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.itinerary)
        XCTAssertNil(vm.error)
    }

    // MARK: - Success

    func test_optimize_success_populatesItinerary_andClearsLoading() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [12, 7], auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertEqual(vm.itinerary?.id, 4)
        XCTAssertEqual(vm.itinerary?.days.first?.stops.count, 2)
        XCTAssertEqual(fake.callCount, 1)
    }

    func test_optimize_forwardsTripIDAndPlaceIDs_andBearerToken() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 42, placeIDs: [1, 2, 3], auth: auth)

        guard case .optimizeTrip(let tripID, let placeIDs, let durationDays, let startTime, let endTime) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 42)
        XCTAssertEqual(placeIDs, [1, 2, 3])
        XCTAssertNil(durationDays)  // çağrıda belirtilmedi -> Otomatik
        XCTAssertEqual(startTime, .defaultStart)  // çağrıda belirtilmedi -> core-api'nin kendi varsayılanı
        XCTAssertEqual(endTime, .defaultEnd)
        XCTAssertEqual(fake.lastToken, "test-token")
    }

    /// Optimizer Yapılandırma ekranında kullanıcı belirli bir gün sayısı
    /// seçtiyse, bu istekle birlikte forward edilmeli — bkz.
    /// TripOptimizerConfigViewModel.durationDays.
    func test_optimize_forwardsDurationDays_whenProvided() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 42, placeIDs: [1, 2, 3], durationDays: 4, auth: auth)

        guard case .optimizeTrip(_, _, let durationDays, _, _) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(durationDays, 4)
    }

    // MARK: - Preferred start/end time forwarding (Req 5: request correctness)

    func test_optimize_forwardsPreferredStartAndEndTime_whenProvided() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(
            tripID: 42, placeIDs: [1, 2, 3],
            preferredStartTime: ClockTime(hour: 7, minute: 30), preferredEndTime: ClockTime(hour: 21, minute: 0),
            auth: auth
        )

        guard case .optimizeTrip(_, _, _, let startTime, let endTime) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(startTime, ClockTime(hour: 7, minute: 30))
        XCTAssertEqual(endTime, ClockTime(hour: 21, minute: 0))
    }

    /// Yalnızca başlangıç saati verildiğinde, bitiş saati core-api'nin kendi
    /// varsayılanına düşmeli — çağıran tarafın bitiş saatini ETKİLEMEMELİ.
    func test_optimize_changingOnlyStartTime_doesNotModifyEndTime() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [1], preferredStartTime: ClockTime(hour: 6, minute: 0), auth: auth)

        guard case .optimizeTrip(_, _, _, let startTime, let endTime) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(startTime, ClockTime(hour: 6, minute: 0))
        XCTAssertEqual(endTime, .defaultEnd)
    }

    /// Yalnızca bitiş saati verildiğinde, başlangıç saati core-api'nin kendi
    /// varsayılanına düşmeli — çağıran tarafın başlangıç saatini
    /// ETKİLEMEMELİ.
    func test_optimize_changingOnlyEndTime_doesNotModifyStartTime() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [1], preferredEndTime: ClockTime(hour: 23, minute: 0), auth: auth)

        guard case .optimizeTrip(_, _, _, let startTime, let endTime) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(startTime, .defaultStart)
        XCTAssertEqual(endTime, ClockTime(hour: 23, minute: 0))
    }

    // MARK: - Error

    func test_optimize_serverError_setsError_leavesItineraryNil() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "INVALID_OPTIMIZATION_REQUEST", message: "En az bir mekan seçmelisiniz."))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [], auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.itinerary)
        XCTAssertEqual(vm.error?.localizedDescription, "En az bir mekan seçmelisiniz.")
    }

    func test_optimize_networkError_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [1], auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertNil(vm.itinerary)
    }

    func test_optimize_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        XCTAssertTrue(auth.isAuthenticated)
        await vm.optimize(tripID: 1, placeIDs: [1], auth: auth)

        // handleUnauthorized() -> logout(): oturum kapanır, VM kendi error
        // alanını set etmez (TripDetailViewModel.load ile aynı davranış).
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.error)
        XCTAssertNil(vm.itinerary)
    }

    // MARK: - Missing token

    func test_optimize_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [1], auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertNil(vm.itinerary)
        XCTAssertFalse(vm.isLoading)
    }

    // MARK: - Loading state

    func test_isLoading_trueWhileRequestInFlight_falseAfterCompletion() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        XCTAssertFalse(vm.isLoading)

        let task = Task { await vm.optimize(tripID: 1, placeIDs: [1], auth: auth) }
        // Task.yield() sayısına güvenmek yerine send()'in fiilen başladığını
        // kesin biçimde bekle — bkz. FakeAPIClient.startedGate.
        await started.wait()

        XCTAssertTrue(vm.isLoading, "İstek gate'te askıda beklerken isLoading true olmalı")

        await proceed.open()
        await task.value

        XCTAssertFalse(vm.isLoading)
        XCTAssertNotNil(vm.itinerary)
    }

    func test_reentrancyGuard_ignoresSecondCallWhileFirstStillLoading() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary())
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let first = Task { await vm.optimize(tripID: 1, placeIDs: [1], auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isLoading)
        XCTAssertEqual(fake.callCount, 1)

        // isLoading true iken ikinci bir çağrı hemen dönmeli, API'yi tekrar çağırmamalı.
        await vm.optimize(tripID: 1, placeIDs: [1], auth: auth)
        XCTAssertEqual(fake.callCount, 1)

        await proceed.open()
        await first.value
        XCTAssertEqual(fake.callCount, 1)
    }

    // MARK: - Edge case: empty result

    func test_optimize_emptyDays_stillPopulatesItinerary_viewDecidesEmptyState() async {
        // ViewModel hiçbir "empty" özel durumu tutmuyor — bu, View'ın
        // itinerary.days.flatMap(\.stops).isEmpty üzerinden türettiği bir
        // durum (bkz. TripOptimizerView). VM yalnızca sunucunun döndürdüğünü taşır.
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary(days: OptimizerFixtures.emptyDays))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.optimize(tripID: 1, placeIDs: [1], auth: auth)

        XCTAssertNotNil(vm.itinerary)
        XCTAssertEqual(vm.itinerary?.days.isEmpty, true)
    }

    // MARK: - Itinerary History: loading a previously saved itinerary

    func test_loadItinerary_fetchesSavedItinerary_populatesItinerary() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary(id: 9))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.loadItinerary(itineraryID: 9, auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertEqual(vm.itinerary?.id, 9)
    }

    /// Itinerary History'den bir satıra dokunmak optimizer'ı TEKRAR
    /// ÇALIŞTIRMAMALI — yalnızca kayıtlı sonucu getirmeli. `.optimizeTrip`
    /// hiç çağrılmamalı, yalnızca `.itineraryDetail`.
    func test_loadItinerary_callsItineraryDetailEndpoint_neverOptimizeEndpoint() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary(id: 9))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.loadItinerary(itineraryID: 9, auth: auth)

        guard case .itineraryDetail(let itineraryID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint)) — .itineraryDetail bekleniyordu")
            return
        }
        XCTAssertEqual(itineraryID, 9)
        XCTAssertEqual(fake.callCount, 1)
        XCTAssertEqual(fake.lastToken, "test-token")
    }

    func test_loadItinerary_serverError_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "ITINERARY_NOT_FOUND", message: "Bu itinerary artık mevcut değil."))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.loadItinerary(itineraryID: 999, auth: auth)

        XCTAssertNil(vm.itinerary)
        XCTAssertEqual(vm.error?.localizedDescription, "Bu itinerary artık mevcut değil.")
    }

    func test_loadItinerary_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        await vm.loadItinerary(itineraryID: 9, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.error)
        XCTAssertNil(vm.itinerary)
    }

    func test_loadItinerary_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary(id: 9))
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = TripOptimizerViewModel()

        await vm.loadItinerary(itineraryID: 9, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertNil(vm.itinerary)
    }

    // MARK: - Apply to Trip — bkz. docs/trip-optimizer.md "Apply semantics"

    func test_applyToTrip_initialState_isNotApplying_hasNoError() {
        let vm = TripOptimizerViewModel()
        XCTAssertFalse(vm.isApplying)
        XCTAssertNil(vm.applyError)
    }

    func test_applyToTrip_success_returnsTrue_clearsApplying_forwardsEndpointAndToken() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.applyResult())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let success = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertTrue(success)
        XCTAssertFalse(vm.isApplying)
        XCTAssertNil(vm.applyError)
        guard case .applyItinerary(let itineraryID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint)) — .applyItinerary bekleniyordu")
            return
        }
        XCTAssertEqual(itineraryID, 4)
        XCTAssertEqual(fake.lastToken, "test-token")
        XCTAssertEqual(fake.callCount, 1)
    }

    /// Saved itinerary (vm.itinerary) apply sırasında dokunulmadan kalmalı —
    /// Req 11: apply, önizlemede gösterilen sonucu MUTASYONA UĞRATMAZ.
    func test_applyToTrip_success_doesNotMutateDisplayedItinerary() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.itinerary(id: 4))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()
        await vm.loadItinerary(itineraryID: 4, auth: auth)
        XCTAssertNotNil(vm.itinerary)

        fake.result = .success(OptimizerFixtures.applyResult(itineraryId: 4))
        _ = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertEqual(vm.itinerary?.id, 4)
        XCTAssertEqual(vm.itinerary?.days.first?.stops.count, 2)
    }

    func test_applyToTrip_serverError_setsApplyError_returnsFalse() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "PERMISSION_DENIED", message: "Bu geziyi düzenleme yetkin yok."))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let success = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertFalse(success)
        XCTAssertFalse(vm.isApplying)
        XCTAssertEqual(vm.applyError, "Bu geziyi düzenleme yetkin yok.")
    }

    func test_applyToTrip_networkError_setsApplyError_returnsFalse() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let success = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertFalse(success)
        XCTAssertNotNil(vm.applyError)
    }

    func test_applyToTrip_unauthorized_logsOutAndDoesNotSetApplyError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        XCTAssertTrue(auth.isAuthenticated)
        let success = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertFalse(success)
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.applyError)
    }

    func test_applyToTrip_noToken_neverCallsAPI_returnsFalse() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.applyResult())
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = TripOptimizerViewModel()

        let success = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(fake.callCount, 0)
    }

    func test_applyToTrip_isApplying_trueWhileRequestInFlight_falseAfterCompletion() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.applyResult())
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        XCTAssertFalse(vm.isApplying)

        let task = Task { await vm.applyToTrip(itineraryID: 4, auth: auth) }
        await started.wait()

        XCTAssertTrue(vm.isApplying, "İstek gate'te askıda beklerken isApplying true olmalı")

        await proceed.open()
        let success = await task.value

        XCTAssertTrue(success)
        XCTAssertFalse(vm.isApplying)
    }

    /// Çift-gönderim koruması: isApplying true iken ikinci bir applyToTrip
    /// çağrısı API'yi tekrar çağırmadan hemen false dönmeli (Req 10: "prevent
    /// double submission" — deleteTrip/optimize ile aynı re-entrancy deseni).
    func test_applyToTrip_reentrancyGuard_ignoresSecondCallWhileFirstInFlight() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.applyResult())
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let first = Task { await vm.applyToTrip(itineraryID: 4, auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isApplying)
        XCTAssertEqual(fake.callCount, 1)

        let secondResult = await vm.applyToTrip(itineraryID: 4, auth: auth)
        XCTAssertFalse(secondResult)
        XCTAssertEqual(fake.callCount, 1)

        await proceed.open()
        let firstResult = await first.value
        XCTAssertTrue(firstResult)
        XCTAssertEqual(fake.callCount, 1)
    }

    /// Req 11: apply'ı tekrar çağırmak (aynı zaten-uygulanmış itinerary için)
    /// hataya düşmemeli — backend idempotent (bkz. sql_optimization_repository
    /// "repeated application" testi). VM tarafında yalnızca çağrının serbestçe
    /// tekrarlanabildiğini doğruluyoruz.
    func test_applyToTrip_repeatedApplication_succeedsAgain() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.applyResult())
        let auth = makeAuth(fake: fake)
        let vm = TripOptimizerViewModel()

        let first = await vm.applyToTrip(itineraryID: 4, auth: auth)
        let second = await vm.applyToTrip(itineraryID: 4, auth: auth)

        XCTAssertTrue(first)
        XCTAssertTrue(second)
        XCTAssertEqual(fake.callCount, 2)
    }
}
