import XCTest
@testable import TripClipApp

@MainActor
final class RegisterViewModelTests: XCTestCase {

    /// `register` başarı yolu GERÇEK Keychain/App Group'a yazar — bir önceki
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
        let vm = RegisterViewModel()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.error)
    }

    // MARK: - canSubmit

    func test_canSubmit_false_whenPasswordTooShort() {
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "abcde"
        XCTAssertFalse(vm.canSubmit)
    }

    /// M36 regression: bu eşik önceden 6'ydı ama sunucunun (ve
    /// `ResetPasswordViewModel`'in) GERÇEK, PAYLAŞILAN kuralı 8 karakter —
    /// 7 karakterlik bir şifre eski istemci kuralını GEÇİYOR ama sunucu
    /// tarafında deterministik olarak 422/VALIDATION_ERROR ile reddediliyordu.
    func test_canSubmit_false_whenPasswordIsSevenCharacters_matchesServerRule() {
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "abcdefg"
        XCTAssertFalse(vm.canSubmit)
    }

    func test_canSubmit_true_whenPasswordIsExactlyEightCharacters() {
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "abcdefgh"
        XCTAssertTrue(vm.canSubmit)
    }

    func test_canSubmit_true_withoutUsername_usernameIsOptional() {
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "password123"
        XCTAssertTrue(vm.canSubmit)
    }

    // MARK: - Success

    func test_register_success_omitsUsername_whenBlank() async {
        let fake = FakeAPIClient()
        fake.result = .success(AuthResponse(
            accessToken: "at", refreshToken: "rt", userId: 1, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = RegisterViewModel()
        vm.email = "  U@Test.com "
        vm.password = "password123"
        vm.username = "   "

        await vm.register(auth: auth)

        XCTAssertNil(vm.error)
        guard case .register(let email, _, let username) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(email, "u@test.com")
        XCTAssertNil(username)
        XCTAssertTrue(auth.isAuthenticated)
    }

    func test_register_success_forwardsTrimmedUsername() async {
        let fake = FakeAPIClient()
        fake.result = .success(AuthResponse(
            accessToken: "at", refreshToken: "rt", userId: 1, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "password123"
        vm.username = "  gezgin  "

        await vm.register(auth: auth)

        guard case .register(_, _, let username) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(username, "gezgin")
    }

    // MARK: - Failure

    func test_register_duplicateEmail_setsServerError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "DUPLICATE_EMAIL", message: "Bu e-posta adresi zaten kayıtlı."))
        let auth = AuthEnvironment(apiClient: fake)
        let vm = RegisterViewModel()
        vm.email = "u@test.com"
        vm.password = "password123"

        await vm.register(auth: auth)

        XCTAssertNotNil(vm.error)
        XCTAssertFalse(auth.isAuthenticated)
    }
}
