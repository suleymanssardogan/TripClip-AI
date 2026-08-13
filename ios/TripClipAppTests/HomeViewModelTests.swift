import XCTest
@testable import TripClipApp

/// `HomeViewModel`in daha önce hiç testi yoktu. M36, `deletePlan`'ın
/// başarısızlık yolunun `load()`'ın KENDİ `error`'ını yeniden kullandığını
/// buldu — `HomeView`in gövdesi `vm.error` varsa TÜM listeyi tam ekran bir
/// hatayla değiştirdiği için, tek bir başarısız silme (ör. geçici bir ağ
/// sorunu) kullanıcının TÜM gezi listesini kaybetmiş gibi görünmesine yol
/// açıyordu. Bu dosya o regresyonu ve `deletePlan`in temel davranışını
/// sabitliyor.
@MainActor
final class HomeViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    private func plan(id: Int) -> PlanSummary {
        PlanSummary(
            id: id, filename: "video.mp4", status: "completed", duration: 30,
            createdAt: "2026-08-01T10:00:00", locationsCount: 3, topLocation: "İstanbul",
            processingTime: 12.0
        )
    }

    func test_initialState_isNotLoading_hasNoPlans_hasNoErrors() {
        let vm = HomeViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertTrue(vm.plans.isEmpty)
        XCTAssertNil(vm.error)
        XCTAssertNil(vm.deleteError)
    }

    func test_deletePlan_success_removesFromList() async {
        let fake = FakeAPIClient()
        fake.result = .success(SuccessResponse(success: true))
        let auth = makeAuth(fake: fake)
        let vm = HomeViewModel()
        vm.setPlansForTesting([plan(id: 1), plan(id: 2)])

        await vm.deletePlan(plan(id: 1), auth: auth)

        XCTAssertEqual(vm.plans.map(\.id), [2])
        XCTAssertNil(vm.deleteError)
    }

    /// M36 regression — bkz. dosya başındaki doc yorumu.
    func test_deletePlan_failure_restoresList_andSetsDeleteErrorNotError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "VIDEO_NOT_FOUND", message: "Bu video artık mevcut değil."))
        let auth = makeAuth(fake: fake)
        let vm = HomeViewModel()
        vm.setPlansForTesting([plan(id: 1), plan(id: 2)])

        await vm.deletePlan(plan(id: 1), auth: auth)

        XCTAssertEqual(vm.plans.map(\.id).sorted(), [1, 2], "Başarısız silme sonrası plan listeye geri KONMALI")
        XCTAssertNotNil(vm.deleteError)
        XCTAssertNil(vm.error, "Silme hatası `load()`'ın `error`'ını KİRLETMEMELİ — aksi halde tüm liste tam ekran bir hatayla değişir")
    }

    func test_deletePlan_unauthorized_logsOutAndDoesNotSetDeleteError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = HomeViewModel()
        vm.setPlansForTesting([plan(id: 1)])

        await vm.deletePlan(plan(id: 1), auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.deleteError)
    }
}
