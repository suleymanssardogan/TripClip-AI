import XCTest
@testable import TripClipApp

@MainActor
final class LoginViewModelTests: XCTestCase {

    /// `login` başarı yolu GERÇEK Keychain/App Group'a yazar — bir önceki
    /// testin bıraktığı durum, sıradaki `AuthEnvironment.init()`'ın
    /// `restoreSession()`'ını yanlışlıkla tetikleyebilir (bkz.
    /// AuthEnvironmentTests.setUp() ile AYNI gerekçe).
    override func setUp() {
        super.setUp()
        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
    }

    /// Bkz. AuthEnvironmentTests.tearDown() — aynı gerekçe: bu dosyanın SON
    /// testi gerçek bir oturum bırakırsa, aynı process içinde SONRA
    /// çalışacak başka test dosyalarını kirletir.
    override func tearDown() {
        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
        super.tearDown()
    }

    // MARK: - Initial state

    func test_initialState_isNotLoading_hasNoError() {
        let vm = LoginViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
    }

    // MARK: - canSubmit

    func test_canSubmit_false_whenEmailIsBlank() {
        let vm = LoginViewModel()
        vm.email = "   "
        vm.password = "password123"
        XCTAssertFalse(vm.canSubmit)
    }

    func test_canSubmit_false_whenPasswordTooShort() {
        let vm = LoginViewModel()
        vm.email = "u@test.com"
        vm.password = "ab"
        XCTAssertFalse(vm.canSubmit)
    }

    func test_canSubmit_true_withValidEmailAndPassword() {
        let vm = LoginViewModel()
        vm.email = "u@test.com"
        vm.password = "password123"
        XCTAssertTrue(vm.canSubmit)
    }

    // MARK: - Success

    func test_login_success_forwardsTrimmedLowercasedEmail() async {
        let fake = FakeAPIClient()
        fake.result = .success(AuthResponse(
            accessToken: "at", refreshToken: "rt", userId: 1, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = LoginViewModel()
        vm.email = "  U@Test.com  "
        vm.password = "password123"

        await vm.login(auth: auth)

        XCTAssertNil(vm.error)
        XCTAssertFalse(vm.isLoading)
        guard case .login(let email, let password) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(email, "u@test.com")
        XCTAssertEqual(password, "password123")
        XCTAssertTrue(auth.isAuthenticated)
    }

    // MARK: - Failure

    func test_login_wrongCredentials_setsError_doesNotAuthenticate() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: "E-posta adresi veya şifre hatalı."))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = LoginViewModel()
        vm.email = "u@test.com"
        vm.password = "wrongpass"

        await vm.login(auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertTrue(vm.error?.isUnauthorized ?? false)
        XCTAssertFalse(auth.isAuthenticated)
    }

    // MARK: - Reentrancy

    func test_login_guardedByCanSubmit_neverCallsAPI_whenAlreadyInvalid() async {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        let vm = LoginViewModel()
        vm.email = ""
        vm.password = ""

        await vm.login(auth: auth)

        XCTAssertEqual(fake.callCount, 0)
    }
}
