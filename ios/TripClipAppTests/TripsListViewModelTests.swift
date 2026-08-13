import XCTest
@testable import TripClipApp

/// `TripsListViewModel`in daha önce hiç testi yoktu. M35, `TripsListView`e
/// `.onAppear`-tetiklemeli bir yeniden yükleme ekledi (bkz. TripsListView.swift
/// doc yorumu — silinen/düzenlenen bir trip'ten geri dönüldüğünde bayat
/// satırları düzeltmek için), bu da `load()`'ın DAHA SIK çağrılacağı anlamına
/// gelir — bu yüzden onun re-entrancy koruması ve temel hata/yetki
/// davranışı burada asgari düzeyde sabitleniyor.
@MainActor
final class TripsListViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    func test_initialState_isNotLoading_hasNoTrips_hasNoError() {
        let vm = TripsListViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertTrue(vm.trips.isEmpty)
        XCTAssertNil(vm.error)
    }

    func test_load_populatesTrips_fromTripListEndpoint() async {
        let fake = FakeAPIClient()
        fake.result = .success(TripListResponse(trips: [
            TripSummary(id: 1, title: "İstanbul", totalDistanceKm: 12.4, createdAt: "2026-08-01T10:00:00", stopsCount: 3),
        ]))
        let auth = makeAuth(fake: fake)
        let vm = TripsListViewModel()

        await vm.load(auth: auth)

        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertEqual(vm.trips.count, 1)
        guard case .tripList = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
    }

    /// `.onAppear` her geri dönüşte `load()`'ı tekrar tetikleyeceği için,
    /// bir önceki isteğin hâlâ devam ederken ikinci bir çağrının ağa
    /// gitmemesi artık daha kritik.
    func test_load_reentrancyGuard_ignoresSecondCallWhileFirstInFlight() async {
        let fake = FakeAPIClient()
        fake.result = .success(TripListResponse(trips: []))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripsListViewModel()

        let first = Task { await vm.load(auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isLoading)

        await vm.load(auth: auth)
        XCTAssertEqual(fake.callCount, 1, "İkinci çağrı ağa hiç gitmemeli")

        await proceed.open()
        await first.value
        XCTAssertEqual(fake.callCount, 1)
    }

    func test_load_noToken_neverCallsAPI() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = TripsListViewModel()

        await vm.load(auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(vm.trips.isEmpty)
    }

    func test_load_unauthorized_logsOutAndDoesNotSetError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripsListViewModel()

        await vm.load(auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.error)
    }

    func test_load_serverError_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "DATABASE_ERROR", message: "Sunucu geçici olarak kullanılamıyor."))
        let auth = makeAuth(fake: fake)
        let vm = TripsListViewModel()

        await vm.load(auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertTrue(vm.trips.isEmpty)
    }
}
