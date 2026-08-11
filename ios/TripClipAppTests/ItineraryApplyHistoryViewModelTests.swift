import XCTest
@testable import TripClipApp

@MainActor
final class ItineraryApplyHistoryViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    // MARK: - Initial state

    func test_initialState_isNotLoading_hasNoEntries_hasNoError() {
        let vm = ItineraryApplyHistoryViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertTrue(vm.entries.isEmpty)
        XCTAssertNil(vm.error)
        XCTAssertNil(vm.undoingID)
        XCTAssertNil(vm.undoError)
    }

    // MARK: - Loading / decoding

    func test_load_populatesEntries_fromApplyHistoryEndpoint() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [
            OptimizerFixtures.applyHistoryEntry(id: 2, isUndo: true, isUndoable: true),
            OptimizerFixtures.applyHistoryEntry(id: 1, isUndoable: false),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertEqual(vm.entries.count, 2)

        guard case .applyHistory(let tripID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 7)
    }

    /// Sunucu zaten en yeniden eskiye döner (bkz. SqlOptimizationRepository.
    /// list_apply_history) — ViewModel bu sırayı olduğu gibi yansıtır.
    func test_load_preservesServerOrder_newestFirst() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [
            OptimizerFixtures.applyHistoryEntry(id: 3, isUndoable: true),
            OptimizerFixtures.applyHistoryEntry(id: 2, isUndoable: false),
            OptimizerFixtures.applyHistoryEntry(id: 1, isUndoable: false),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertEqual(vm.entries.map(\.id), [3, 2, 1])
    }

    /// Req "latest item marked undoable" / "non-latest item cannot trigger
    /// undo" — bu bayrak sunucudan gelir, istemci TÜRETMEZ; burada yalnızca
    /// doğru şekilde deşifre edilip yansıtıldığı doğrulanıyor.
    func test_load_onlyLatestEntry_isMarkedUndoable() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [
            OptimizerFixtures.applyHistoryEntry(id: 2, isUndoable: true),
            OptimizerFixtures.applyHistoryEntry(id: 1, isUndoable: false),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertTrue(vm.entries[0].isUndoable)
        XCTAssertFalse(vm.entries[1].isUndoable)
    }

    /// Req "deleted itinerary history representation" — `itineraryId` `nil`
    /// olduğunda ViewModel/model katmanı bunu olduğu gibi taşır; sunum
    /// (ör. "Silinmiş optimizasyon") View katmanının sorumluluğu.
    func test_load_deletedItineraryEntry_hasNilItineraryId() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [
            OptimizerFixtures.applyHistoryEntry(id: 1, itineraryId: nil, itineraryCreatedAt: nil, isUndoable: true),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertNil(vm.entries[0].itineraryId)
    }

    func test_load_emptyHistory_noError() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: []))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertTrue(vm.entries.isEmpty)
        XCTAssertNil(vm.error)
    }

    func test_load_networkError_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertTrue(vm.entries.isEmpty)
    }

    func test_load_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.error)
    }

    func test_load_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [OptimizerFixtures.applyHistoryEntry(id: 1)]))
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = ItineraryApplyHistoryViewModel()

        await vm.load(tripID: 7, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(vm.entries.isEmpty)
    }

    func test_load_reentrancyGuard_ignoresSecondLoadWhileFirstStillLoading() async {
        let fake = FakeAPIClient()
        fake.result = .success(ApplyHistoryListResponse(entries: [OptimizerFixtures.applyHistoryEntry(id: 1)]))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        let first = Task { await vm.load(tripID: 7, auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isLoading)

        await vm.load(tripID: 7, auth: auth)
        XCTAssertEqual(fake.callCount, 1)

        await proceed.open()
        await first.value
        XCTAssertEqual(fake.callCount, 1)
    }

    // MARK: - Undo

    func test_undo_success_returnsTrue_clearsUndoingID() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.undoResult())
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        let success = await vm.undo(historyID: 2, tripID: 7, auth: auth)

        XCTAssertTrue(success)
        XCTAssertNil(vm.undoingID)
        XCTAssertNil(vm.undoError)

        guard case .undoApplyHistory(let tripID, let historyID) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 7)
        XCTAssertEqual(historyID, 2)
    }

    func test_undo_failure_setsUndoError_returnsFalse() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "STALE_UNDO", message: "Yalnızca en son uygulama geri alınabilir."))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        let success = await vm.undo(historyID: 1, tripID: 7, auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(vm.undoError, "Yalnızca en son uygulama geri alınabilir.")
        XCTAssertNil(vm.undoingID)
    }

    func test_undo_doubleSubmission_isPrevented() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.undoResult())
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        let first = Task { await vm.undo(historyID: 2, tripID: 7, auth: auth) }
        await started.wait()
        XCTAssertEqual(vm.undoingID, 2)

        let secondAttempt = await vm.undo(historyID: 2, tripID: 7, auth: auth)
        XCTAssertFalse(secondAttempt, "İkinci (eş zamanlı) çağrı görmezden gelinmeli")

        await proceed.open()
        let firstResult = await first.value
        XCTAssertTrue(firstResult)
        XCTAssertEqual(fake.callCount, 1, "İkinci undo denemesi hiç ağa gitmemeli")
    }

    func test_undo_unauthorized_logsOutAndDoesNotSetUndoError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = ItineraryApplyHistoryViewModel()

        let success = await vm.undo(historyID: 1, tripID: 7, auth: auth)

        XCTAssertFalse(success)
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.undoError)
    }

    func test_undo_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        fake.result = .success(OptimizerFixtures.undoResult())
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = ItineraryApplyHistoryViewModel()

        let success = await vm.undo(historyID: 1, tripID: 7, auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(fake.callCount, 0)
    }

    // MARK: - Trip isolation

    /// İki AYRI `ItineraryApplyHistoryViewModel` örneği, HER BİRİ tek bir
    /// trip'i temsil eder (bu ekran zaten `tripID`'ye göre yükleniyor) —
    /// birinin `load()`/`undo()`'su diğerinin `entries`'ini hiç etkilemez.
    func test_tripIsolation_loadingOneTripsHistory_neverAffectsAnothers() async {
        let fakeA = FakeAPIClient()
        fakeA.result = .success(ApplyHistoryListResponse(entries: [OptimizerFixtures.applyHistoryEntry(id: 1)]))
        let authA = makeAuth(fake: fakeA)
        let vmA = ItineraryApplyHistoryViewModel()
        await vmA.load(tripID: 10, auth: authA)

        let fakeB = FakeAPIClient()
        fakeB.result = .success(ApplyHistoryListResponse(entries: []))
        let authB = makeAuth(fake: fakeB)
        let vmB = ItineraryApplyHistoryViewModel()
        await vmB.load(tripID: 20, auth: authB)

        XCTAssertEqual(vmA.entries.count, 1)
        XCTAssertTrue(vmB.entries.isEmpty)
    }
}
