import AuthenticationServices
import XCTest
@testable import TripClipApp

@MainActor
final class AuthEnvironmentTests: XCTestCase {

    /// `login`/`register`/`googleSignIn` başarı yolu GERÇEK Keychain/App Group'a
    /// yazar (`setUserForTesting` gibi bir bypass kullanmazlar — burada asıl
    /// test edilen tam da bu kalıcılık). Bu yüzden bir önceki testin bıraktığı
    /// GERÇEK Keychain durumu, sıradaki testin `AuthEnvironment.init()`'ındaki
    /// `restoreSession()`'ı YANLIŞLIKLA tetikleyip "başarısız login sonrası hâlâ
    /// authenticated" gibi sahte bir pozitif üretebilir — testler arası izolasyon
    /// için her testten önce temizleniyor.
    override func setUp() {
        super.setUp()
        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
    }

    /// Yalnızca BAŞTA temizlemek yetmez — bu dosyanın SON testi gerçek bir
    /// oturum bırakırsa, aynı process içinde SONRA çalışacak BAŞKA test
    /// dosyalarını (ör. TripAssistantViewModelTests'in `withUser: false`
    /// senaryosu) kirletir: onların `AuthEnvironment.init()`'ı da AYNI
    /// gerçek Keychain'i okur. Bu, gerçekten TripAssistantViewModelTests'te
    /// gözlemlenen bir tam-suite sızıntısıydı — kökeni burada.
    override func tearDown() {
        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
        super.tearDown()
    }

    // MARK: - Login / Register persist session

    func test_login_success_persistsUserAndSetsAuthenticated() async throws {
        let fake = FakeAPIClient()
        fake.result = .success(AuthResponse(
            accessToken: "at", refreshToken: "rt", userId: 9, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)

        try await auth.login(email: "u@test.com", password: "password123")

        XCTAssertTrue(auth.isAuthenticated)
        XCTAssertEqual(auth.user?.id, 9)
        XCTAssertEqual(auth.user?.email, "u@test.com")
        XCTAssertEqual(auth.user?.token, "at")
    }

    func test_login_failure_doesNotAuthenticate() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: "E-posta adresi veya şifre hatalı."))
        let auth = AuthEnvironment(apiClient: fake)

        do {
            try await auth.login(email: "u@test.com", password: "wrong")
            XCTFail("Hata bekleniyordu")
        } catch {
            XCTAssertFalse(auth.isAuthenticated)
        }
    }

    // MARK: - Apple Sign In

    /// M36 regression: kullanıcı sistem Apple Sign-In sayfasını iptal
    /// ettiğinde `result` `.failure(ASAuthorizationError.canceled)` olur —
    /// bu, "Apple ile giriş başarısız." (genel `guard`in `else` dalı)
    /// DEĞİL, ayrı ve daha nazik bir mesaj almalı (Google'ın kendi
    /// `.cancelled` işlemesiyle tutarlı).
    func test_appleSignIn_userCancelled_throwsDistinctCancelledError_notGenericFailure() async {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        let cancelledResult: Result<ASAuthorization, Error> = .failure(ASAuthorizationError(.canceled))

        do {
            try await auth.appleSignIn(result: cancelledResult)
            XCTFail("Hata bekleniyordu")
        } catch let apiError as APIError {
            guard case .server(let code, let message) = apiError else {
                XCTFail("Beklenmeyen hata tipi: \(apiError)"); return
            }
            XCTAssertEqual(code, "APPLE_AUTH_CANCELLED")
            XCTAssertEqual(message, "Apple girişi iptal edildi.")
            XCTAssertNotEqual(message, "Apple ile giriş başarısız.", "İptal, genel başarısızlık mesajını GÖSTERMEMELİ")
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertEqual(fake.callCount, 0, "İptal edilen bir girişte core-api'ye HİÇ istek gitmemeli")
    }

    // MARK: - Google Sign In

    /// `appleSignIn`'le AYNI akış: yalnızca tek kullanımlık `code`/`redirectUri`
    /// core-api'ye iletilir, gerçek doğrulama/token değişimi sunucuda yapılır.
    func test_googleSignIn_success_persistsUserAndForwardsCodeAndRedirectUri() async throws {
        let fake = FakeAPIClient()
        fake.result = .success(AuthResponse(
            accessToken: "at", refreshToken: "rt", userId: 5, email: "g@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)

        try await auth.googleSignIn(code: "authcode", redirectUri: "com.sardogan.TripClipAI:/oauth2redirect")

        XCTAssertTrue(auth.isAuthenticated)
        XCTAssertEqual(auth.user?.id, 5)
        guard case .googleSignIn(let code, let redirectUri) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(code, "authcode")
        XCTAssertEqual(redirectUri, "com.sardogan.TripClipAI:/oauth2redirect")
    }

    func test_googleSignIn_unverifiedEmailConflict_throwsWithoutAuthenticating() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(
            code: "GOOGLE_EMAIL_NOT_VERIFIED",
            message: "Bu e-posta adresiyle zaten bir hesap var. Lütfen normal giriş yapın."
        ))
        let auth = AuthEnvironment(apiClient: fake)

        do {
            try await auth.googleSignIn(code: "authcode", redirectUri: "http://localhost:3000/auth/google/callback")
            XCTFail("Hata bekleniyordu")
        } catch let apiError as APIError {
            guard case .server(let code, _) = apiError else {
                XCTFail("Beklenmeyen hata tipi: \(apiError)")
                return
            }
            XCTAssertEqual(code, "GOOGLE_EMAIL_NOT_VERIFIED")
            XCTAssertFalse(auth.isAuthenticated)
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    // MARK: - Forgot / Reset Password

    func test_forgotPassword_forwardsEmail_doesNotAuthenticate() async throws {
        let fake = FakeAPIClient()
        fake.result = .success(StatusResponse(status: "ok"))
        let auth = AuthEnvironment(apiClient: fake)

        try await auth.forgotPassword(email: "u@test.com")

        guard case .forgotPassword(let email) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(email, "u@test.com")
        XCTAssertFalse(auth.isAuthenticated)
    }

    func test_resetPassword_forwardsTokenAndNewPassword_doesNotAuthenticate() async throws {
        let fake = FakeAPIClient()
        fake.result = .success(StatusResponse(status: "ok"))
        let auth = AuthEnvironment(apiClient: fake)

        try await auth.resetPassword(token: "reset-token", newPassword: "newpassword123")

        guard case .resetPassword(let token, let newPassword) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(token, "reset-token")
        XCTAssertEqual(newPassword, "newpassword123")
        // Şifre sıfırlama tek başına bir oturum AÇMAZ — kullanıcı hâlâ
        // yeni şifresiyle ayrıca giriş yapmalı (bkz. reset-password sonrası
        // web'in /login'e yönlendirmesiyle AYNI davranış).
        XCTAssertFalse(auth.isAuthenticated)
    }

    func test_resetPassword_invalidToken_throws() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "PASSWORD_RESET_TOKEN_INVALID", message: "Bu şifre sıfırlama linki geçersiz."))
        let auth = AuthEnvironment(apiClient: fake)

        do {
            try await auth.resetPassword(token: "bad-token", newPassword: "newpassword123")
            XCTFail("Hata bekleniyordu")
        } catch {
            XCTAssertFalse(auth.isAuthenticated)
        }
    }

    // MARK: - Token Refresh (M35)

    /// Bu, M35 audit'inde bulunan gerçek yarış koşulunun deterministik
    /// regresyon testidir: `TripDetailView`'ın üç paralel `.task`'ı gibi
    /// birden fazla eşzamanlı çağırıcı aynı anda süresi dolmuş bir token
    /// görürse, düzeltme ÖNCESİ her biri KENDİ `/auth/refresh` isteğini
    /// ateşliyordu — biri başarıyla yeni bir çift kalıcı hale getirirken
    /// diğeri artık geçersiz olan AYNI eski refresh token'ı kullanmaya
    /// çalışıp reddediliyor ve KOŞULSUZCA `handleUnauthorized()`/logout
    /// tetikleyip BİRAZ ÖNCE başarıyla yenilenmiş GEÇERLİ oturumu siliyordu.
    /// Düzeltme (`AuthEnvironment.inFlightRefresh`), ikinci çağıranın BİRİNCİ
    /// çağıranın devam eden Task'ını PAYLAŞMASINI sağlar — bu test, gerçek
    /// ağ çağrısının (`fake.callCount`) TAM OLARAK BİR kez yapıldığını
    /// doğrulayarak bunu kanıtlar.
    func test_validAccessToken_concurrentCallsWithExpiredToken_shareASingleRefreshRequest() async {
        let fake = FakeAPIClient()
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        fake.result = .success(AuthResponse(
            accessToken: "new-at", refreshToken: "new-rt", userId: 1, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)
        // Herhangi bir çözümlenemeyen/geçersiz string JWT.isExpired tarafından
        // "süresi dolmuş" sayılır (bkz. JWT.swift'in kendi "okunamayan token'ı
        // güvenli tarafta say" ilkesi) — gerçek bir JWT üretmeye gerek yok.
        auth.setUserForTesting(AuthUser(id: 1, email: "u@test.com", token: "not-a-real-jwt"))
        KeychainStore.saveRefresh("old-refresh-token")

        let first = Task { await auth.validAccessToken() }
        await started.wait()  // ilk çağrının send()'i başladı — inFlightRefresh artık set edilmiş olmalı

        let second = Task { await auth.validAccessToken() }
        // second'ın KENDİ send() çağrısını yapmadan, doğrudan mevcut Task'ı
        // paylaştığını doğrulamak için: gate hâlâ kapalıyken second'ın da
        // sonuçlanabilmesi (aşağıda) YALNIZCA dedup çalışıyorsa mümkündür —
        // aksi halde second kendi send()'inde AYNI gate'e takılıp kalır ve
        // `proceed.open()` her iki send()'i de serbest bırakır, callCount 2 olur.

        await proceed.open()
        let firstToken = await first.value
        let secondToken = await second.value

        XCTAssertEqual(firstToken, "new-at")
        XCTAssertEqual(secondToken, "new-at")
        XCTAssertEqual(fake.callCount, 1, "İki eşzamanlı çağrı TEK bir /auth/refresh isteği paylaşmalı, ikisi AYRI ateşlememeli")
        XCTAssertTrue(auth.isAuthenticated, "Yarışın kaybeden tarafı, BAŞARILI şekilde yenilenmiş oturumu SİLMEMELİ")

        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
    }

    // MARK: - Logout during an in-flight refresh (M39)

    /// M39 audit bulgusu: bir refresh isteği DEVAM EDERKEN kullanıcı logout
    /// olursa, sunucudan BAŞARILI bir yanıt gelse bile bu sonuç artık
    /// GEÇERSİZ sayılmalı — aksi halde `persist()` logout'u sessizce geri
    /// alır (Keychain'e YENİ bir geçerli token çifti yazarak, oturumu
    /// "diriltir"). `sessionEpoch`, `logout()`'un kendi ağ çağrısıyla (fake'in
    /// tek `result`'ıyla tip çakışmasını önlemek için burada refresh token'ı
    /// gate açılmadan ÖNCE Keychain'den siliyoruz — `logout()` böylece kendi
    /// best-effort bildirimini ATLAR, ama zaten YAKALANMIŞ olan in-flight
    /// refresh'in kendi yerel `refreshToken` değişkenini ETKİLEMEZ; test
    /// ettiğimiz yarış tam olarak aynı kalır) bu geç gelen yanıtın SESSİZCE
    /// uygulanmasını yapısal olarak engeller.
    func test_refreshCompletingAfterLogout_doesNotResurrectSession() async {
        let fake = FakeAPIClient()
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        fake.result = .success(AuthResponse(
            accessToken: "new-at", refreshToken: "new-rt", userId: 1, email: "u@test.com", tokenType: "bearer"
        ))
        let auth = AuthEnvironment(apiClient: fake)
        auth.setUserForTesting(AuthUser(id: 1, email: "u@test.com", token: "not-a-real-jwt"))
        KeychainStore.saveRefresh("old-refresh-token")

        let refreshTask = Task { await auth.validAccessToken() }
        await started.wait()  // refresh isteği başladı (kendi refreshToken'ını zaten yakaladı), henüz sonuçlanmadı

        // logout()'un KENDİ best-effort ağ çağrısını atlaması için — aksi
        // halde fake'in tek `result`'ı (bir AuthResponse) logout'un beklediği
        // StatusResponse tipine dönüştürülemeyip test'i çökertirdi. Zaten
        // devam eden refresh isteği bundan ETKİLENMEZ (yukarıdaki yorum).
        KeychainStore.deleteRefresh()
        auth.logout()
        XCTAssertFalse(auth.isAuthenticated, "logout() hemen etkili olmalı")

        await proceed.open()  // gecikmiş refresh yanıtı ŞİMDİ, logout SONRASI döner
        let result = await refreshTask.value

        XCTAssertNil(result, "Logout sonrası tamamlanan bir refresh, yeni bir token DÖNDÜRMEMELİ")
        XCTAssertFalse(auth.isAuthenticated, "Gecikmiş refresh yanıtı logout'u SESSİZCE GERİ ALMAMALI")
        XCTAssertNil(auth.user)

        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
    }

    // MARK: - Logout

    func test_logout_clearsUser() {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        auth.setUserForTesting(AuthUser(id: 1, email: "u@test.com", token: "at"))
        XCTAssertTrue(auth.isAuthenticated)

        auth.logout()

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(auth.user)
    }

    func test_handleUnauthorized_logsOutCurrentUser() {
        let fake = FakeAPIClient()
        let auth = AuthEnvironment(apiClient: fake)
        auth.setUserForTesting(AuthUser(id: 1, email: "u@test.com", token: "at"))

        auth.handleUnauthorized()

        XCTAssertFalse(auth.isAuthenticated)
    }
}
