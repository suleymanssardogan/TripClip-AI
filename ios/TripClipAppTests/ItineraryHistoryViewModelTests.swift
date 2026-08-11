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

    // MARK: - Delete (Milestone 19 — Delete Saved Itinerary from History)

    private func loaded(_ summaries: [ItinerarySummary], fake: FakeAPIClient, tripID: Int = 7) async -> (ItineraryHistoryViewModel, AuthEnvironment) {
        fake.result = .success(ItineraryListResponse(itineraries: summaries))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryHistoryViewModel()
        await vm.load(tripID: tripID, auth: auth)
        return (vm, auth)
    }

    func test_deleteItinerary_success_removesCorrectRow() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([
            OptimizerFixtures.summary(id: 1), OptimizerFixtures.summary(id: 2), OptimizerFixtures.summary(id: 3),
        ], fake: fake)

        fake.result = .success(SuccessResponse(success: true))
        let success = await vm.deleteItinerary(id: 2, auth: auth)

        XCTAssertTrue(success)
        XCTAssertEqual(vm.itineraries.map(\.id), [1, 3])
        guard case .deleteItinerary(let deletedID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(deletedID, 2)
    }

    /// Req "ordering remains correct" — kalan öğelerin göreli sırası,
    /// silinen öğe hangi konumda olursa olsun BOZULMAMALI (dizi yeniden
    /// sıralanmıyor, yalnızca ilgili eleman çıkarılıyor).
    func test_deleteItinerary_success_preservesOrderingOfRemainingItems() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([
            OptimizerFixtures.summary(id: 5), OptimizerFixtures.summary(id: 2), OptimizerFixtures.summary(id: 9), OptimizerFixtures.summary(id: 1),
        ], fake: fake)

        fake.result = .success(SuccessResponse(success: true))
        await vm.deleteItinerary(id: 9, auth: auth)

        XCTAssertEqual(vm.itineraries.map(\.id), [5, 2, 1])
    }

    func test_deleteItinerary_failure_leavesRowIntact() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1), OptimizerFixtures.summary(id: 2)], fake: fake)

        fake.result = .failure(APIError.server(code: "ITINERARY_NOT_FOUND", message: "Bulunamadı."))
        let success = await vm.deleteItinerary(id: 1, auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(vm.itineraries.map(\.id), [1, 2], "Başarısız silme öğeyi listede BIRAKMALI")
        XCTAssertEqual(vm.deleteError, "Bulunamadı.")
    }

    func test_deleteItinerary_doubleSubmission_isPrevented() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1)], fake: fake)

        fake.result = .success(SuccessResponse(success: true))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed

        let first = Task { await vm.deleteItinerary(id: 1, auth: auth) }
        await started.wait()
        XCTAssertEqual(vm.deletingID, 1)

        let secondAttemptResult = await vm.deleteItinerary(id: 1, auth: auth)
        XCTAssertFalse(secondAttemptResult, "İkinci (eş zamanlı) çağrı görmezden gelinmeli")

        await proceed.open()
        let firstResult = await first.value
        XCTAssertTrue(firstResult)
        XCTAssertNil(vm.deletingID)
        // Yalnızca BİR ağ isteği yapıldı — "load" (listeleme, ayrı endpoint)
        // dışında `deleteItinerary` çağrılarından yalnızca 1 tanesi
        // sağlayıcıya ulaştı.
        XCTAssertEqual(fake.callCount, 2, "1 load() + 1 delete() — ikinci delete denemesi hiç ağa gitmemeli")
    }

    func test_deleteItinerary_doesNotAlterOtherItineraries() async {
        let fake = FakeAPIClient()
        let originalOthers = [
            OptimizerFixtures.summary(id: 2, score: 55), OptimizerFixtures.summary(id: 3, score: 91),
        ]
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1)] + originalOthers, fake: fake)

        fake.result = .success(SuccessResponse(success: true))
        await vm.deleteItinerary(id: 1, auth: auth)

        XCTAssertEqual(vm.itineraries, originalOthers)
    }

    /// Req "empty-history state appears after deleting the last entry" —
    /// View'ın kendi `vm.itineraries.isEmpty` koşulu zaten emptyState'i
    /// tetikliyor (bkz. ItineraryHistoryView.body), bu yüzden bu test
    /// yalnızca dizinin GERÇEKTEN boşaldığını doğruluyor.
    func test_deleteItinerary_deletingLastEntry_resultsInEmptyItineraries() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1)], fake: fake)

        fake.result = .success(SuccessResponse(success: true))
        await vm.deleteItinerary(id: 1, auth: auth)

        XCTAssertTrue(vm.itineraries.isEmpty)
    }

    /// Req "error state can be retried" — başarısız bir denemeden sonra
    /// `deletingID` sıfırlanmış olmalı ki AYNI (ya da başka) bir silme
    /// tekrar denenebilsin.
    func test_deleteItinerary_afterFailure_canBeRetriedSuccessfully() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1)], fake: fake)

        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let firstAttempt = await vm.deleteItinerary(id: 1, auth: auth)
        XCTAssertFalse(firstAttempt)
        XCTAssertNil(vm.deletingID)
        XCTAssertEqual(vm.itineraries.map(\.id), [1])

        fake.result = .success(SuccessResponse(success: true))
        let retry = await vm.deleteItinerary(id: 1, auth: auth)
        XCTAssertTrue(retry)
        XCTAssertTrue(vm.itineraries.isEmpty)
    }

    func test_deleteItinerary_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        let (vm, auth) = await loaded([OptimizerFixtures.summary(id: 1)], fake: fake)

        fake.result = .failure(APIError.unauthorized(message: nil))
        let success = await vm.deleteItinerary(id: 1, auth: auth)

        XCTAssertFalse(success)
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.deleteError)
        XCTAssertEqual(vm.itineraries.map(\.id), [1], "401'de öğe listede kalmalı — silinmedi")
    }

    func test_deleteItinerary_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(SuccessResponse(success: true))
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = ItineraryHistoryViewModel()

        let success = await vm.deleteItinerary(id: 1, auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(fake.callCount, 0, "Token yoksa ağa hiç gidilmemeli")
    }

    /// Trip izolasyonu: bu ViewModel yalnızca KENDİ `tripID`'si için
    /// yüklenmiş listeyi tutar — `deleteItinerary` yalnızca o dizideki
    /// eşleşen id'yi çıkarır, başka bir trip'in verisiyle hiçbir etkileşimi
    /// yok (ViewModel zaten tek bir trip'in geçmişini temsil ediyor, bkz.
    /// `ItineraryHistoryView.tripID`).
    func test_deleteItinerary_tripIsolation_onlyAffectsThisViewModelsOwnList() async {
        let fakeA = FakeAPIClient()
        let (vmA, authA) = await loaded([OptimizerFixtures.summary(id: 1), OptimizerFixtures.summary(id: 2)], fake: fakeA, tripID: 10)

        let fakeB = FakeAPIClient()
        let (vmB, authB) = await loaded([OptimizerFixtures.summary(id: 1), OptimizerFixtures.summary(id: 2)], fake: fakeB, tripID: 20)

        fakeA.result = .success(SuccessResponse(success: true))
        await vmA.deleteItinerary(id: 1, auth: authA)

        XCTAssertEqual(vmA.itineraries.map(\.id), [2])
        XCTAssertEqual(vmB.itineraries.map(\.id), [1, 2], "Trip B'nin listesi Trip A'daki silmeden HİÇ etkilenmemeli")
    }
}
