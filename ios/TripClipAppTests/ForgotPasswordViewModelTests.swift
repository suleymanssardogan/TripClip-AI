import XCTest
@testable import TripClipApp

@MainActor
final class ForgotPasswordViewModelTests: XCTestCase {

    func test_initialState_isNotLoading_hasNotSubmitted() {
        let vm = ForgotPasswordViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertFalse(vm.didSubmit)
    }

    func test_canSubmit_false_whenEmailIsBlank() {
        let vm = ForgotPasswordViewModel()
        vm.email = "   "
        XCTAssertFalse(vm.canSubmit)
    }

    func test_submit_success_forwardsTrimmedLowercasedEmail_andMarksSubmitted() async {
        let fake = FakeAPIClient()
        fake.result = .success(StatusResponse(status: "ok"))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ForgotPasswordViewModel()
        vm.email = "  U@Test.com  "

        await vm.submit(auth: auth)

        XCTAssertTrue(vm.didSubmit)
        XCTAssertFalse(vm.isLoading)
        guard case .forgotPassword(let email) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(email, "u@test.com")
    }

    /// Anti-enumeration: sunucu hatası bile olsa AYNI genel "başarı" durumuna
    /// geçilir — bir hesabın var olup olmadığını farklı davranışla İMA
    /// ETMEMEK için (bkz. AuthService.request_password_reset'in AYNI kararı,
    /// web'in forgot-password sayfasının AYNI davranışı).
    func test_submit_serverError_stillMarksSubmitted() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ForgotPasswordViewModel()
        vm.email = "u@test.com"

        await vm.submit(auth: auth)

        XCTAssertTrue(vm.didSubmit)
    }

    func test_submit_guardedByCanSubmit_neverCallsAPI_whenEmailBlank() async {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ForgotPasswordViewModel()
        vm.email = ""

        await vm.submit(auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertFalse(vm.didSubmit)
    }
}
