import XCTest
@testable import TripClipApp

@MainActor
final class ResetPasswordViewModelTests: XCTestCase {

    func test_initialState_isNotLoading_hasNoError_hasNotSucceeded() {
        let vm = ResetPasswordViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
        XCTAssertFalse(vm.didSucceed)
    }

    func test_canSubmit_false_whenTokenIsBlank() {
        let vm = ResetPasswordViewModel()
        vm.token = "  "
        vm.newPassword = "newpassword123"
        XCTAssertFalse(vm.canSubmit)
    }

    func test_canSubmit_false_whenPasswordTooShort() {
        let vm = ResetPasswordViewModel()
        vm.token = "abc123"
        vm.newPassword = "short1"
        XCTAssertFalse(vm.canSubmit)
    }

    func test_submit_mismatchedPasswords_setsErrorClientSide_neverCallsAPI() async {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ResetPasswordViewModel()
        vm.token = "abc123"
        vm.newPassword = "newpassword123"
        vm.confirmPassword = "different123"

        await vm.submit(auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertNotNil(vm.error)
        XCTAssertFalse(vm.didSucceed)
    }

    func test_submit_success_forwardsTrimmedToken_andMarksSucceeded() async {
        let fake = FakeAPIClient()
        fake.result = .success(StatusResponse(status: "ok"))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ResetPasswordViewModel()
        vm.token = "  abc123  "
        vm.newPassword = "newpassword123"
        vm.confirmPassword = "newpassword123"

        await vm.submit(auth: auth)

        XCTAssertTrue(vm.didSucceed)
        XCTAssertNil(vm.error)
        guard case .resetPassword(let token, let newPassword) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(token, "abc123")
        XCTAssertEqual(newPassword, "newpassword123")
    }

    func test_submit_expiredToken_setsServerError_doesNotMarkSucceeded() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(
            code: "PASSWORD_RESET_TOKEN_EXPIRED",
            message: "Bu şifre sıfırlama linkinin süresi doldu. Yeni bir istek gönderin."
        ))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = ResetPasswordViewModel()
        vm.token = "expired-token"
        vm.newPassword = "newpassword123"
        vm.confirmPassword = "newpassword123"

        await vm.submit(auth: auth)

        XCTAssertFalse(vm.didSucceed)
        XCTAssertNotNil(vm.error)
    }
}
