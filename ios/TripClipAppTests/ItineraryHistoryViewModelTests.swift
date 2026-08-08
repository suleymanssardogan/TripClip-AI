import XCTest
@testable import TripClipApp

@MainActor
final class ItineraryHistoryViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    // MARK: - Initial state

    func test_initialState_isNotLoading_hasNoItineraries_hasNoError() {
        let vm = ItineraryHistoryViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertTrue(vm.itineraries.isEmpty)
        XCTAssertNil(vm.error)
    }

    // MARK: - History loading

    func test_load_populatesItineraries_fromTripsItinerariesEndpoint() async {
        let fake = FakeAPIClient()
        fake.result = .success(ItineraryListResponse(itineraries: [
            OptimizerFixtures.summary(id: 1, createdAt: "2026-08-01T09:00:00"),
            OptimizerFixtures.summary(id: 2, createdAt: "2026-08-02T09:00:00"),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertEqual(vm.itineraries.count, 2)

        guard case .itineraries(let tripID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 7)
    }

    // MARK: - Newest-first ordering

    func test_sortedNewestFirst_isPureFunctionOrderingByCreatedAtDescending() {
        let oldest = OptimizerFixtures.summary(id: 1, createdAt: "2026-08-01T09:00:00")
        let middle = OptimizerFixtures.summary(id: 2, createdAt: "2026-08-05T09:00:00")
        let newest = OptimizerFixtures.summary(id: 3, createdAt: "2026-08-08T09:00:00")

        let sorted = ItineraryHistoryViewModel.sortedNewestFirst([oldest, newest, middle])

        XCTAssertEqual(sorted.map(\.id), [3, 2, 1])
    }

    func test_load_ordersItinerariesNewestFirst_evenIfServerReturnsThemOutOfOrder() async {
        // Sunucu normalde zaten created_at DESC döner (bkz.
        // SqlOptimizationRepository.list_itineraries) — bu test istemci-taraflı
        // savunma katmanının GERÇEKTEN sıraladığını, sunucuya körü körüne
        // güvenmediğini doğruluyor.
        let fake = FakeAPIClient()
        fake.result = .success(ItineraryListResponse(itineraries: [
            OptimizerFixtures.summary(id: 1, createdAt: "2026-08-01T09:00:00"),  // en eski, ilk sırada geldi
            OptimizerFixtures.summary(id: 3, createdAt: "2026-08-08T09:00:00"),  // en yeni
            OptimizerFixtures.summary(id: 2, createdAt: "2026-08-05T09:00:00"),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertEqual(vm.itineraries.map(\.id), [3, 2, 1])
    }

    // MARK: - Empty state

    func test_load_emptyHistory_resultsInEmptyItineraries_noError() async {
        let fake = FakeAPIClient()
        fake.result = .success(ItineraryListResponse(itineraries: []))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertTrue(vm.itineraries.isEmpty)
        XCTAssertNil(vm.error)
        XCTAssertFalse(vm.isLoading)
    }

    // MARK: - API failure

    func test_load_networkError_setsError_leavesItinerariesEmpty() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertTrue(vm.itineraries.isEmpty)
    }

    func test_load_tripNotFound_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "TRIP_NOT_FOUND", message: "Bu gezi artık mevcut değil."))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 999, auth: auth)

        XCTAssertEqual(vm.error?.localizedDescription, "Bu gezi artık mevcut değil.")
    }

    func test_load_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.error)
        XCTAssertTrue(vm.itineraries.isEmpty)
    }

    func test_load_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(ItineraryListResponse(itineraries: [OptimizerFixtures.summary(id: 1)]))
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = ItineraryHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(vm.itineraries.isEmpty)
    }

    // MARK: - Re-entrancy guard (same convention as TripOptimizerViewModel)

    func test_reentrancyGuard_ignoresSecondLoadWhileFirstStillLoading() async {
        let fake = FakeAPIClient()
        fake.result = .success(ItineraryListResponse(itineraries: [OptimizerFixtures.summary(id: 1)]))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()

        let first = Task { await vm.load(tripID: 7, auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isLoading)

        await vm.load(tripID: 7, auth: auth)
        XCTAssertEqual(fake.callCount, 1)

        await proceed.open()
        await first.value
        XCTAssertEqual(fake.callCount, 1)
    }
}
