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

        guard case .optimizeTrip(let tripID, let placeIDs) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 42)
        XCTAssertEqual(placeIDs, [1, 2, 3])
        XCTAssertEqual(fake.lastToken, "test-token")
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
}
