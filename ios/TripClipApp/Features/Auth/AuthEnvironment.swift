import SwiftUI
import AuthenticationServices
import OSLog

// MARK: - AuthEnvironment

@MainActor
@Observable
final class AuthEnvironment {

    // MARK: Published State

    private(set) var user:   AuthUser?
    private(set) var isLoading = false

    var isAuthenticated: Bool { user != nil }

    // MARK: Dependencies

    /// Protokol tipinde (somut `APIClient` değil) — testlerin `APIClientProtocol`'e
    /// uyan bir sahte istemci enjekte edebilmesi için. Üretimde her zaman gerçek
    /// `APIClient` (varsayılan parametre), davranış değişmiyor.
    let apiClient: APIClientProtocol

    // MARK: Init

    init(apiClient: APIClientProtocol = APIClient()) {
        self.apiClient = apiClient
        // refreshHandler yalnızca somut APIClient'ta var (protokolün parçası
        // değil) — testlerde enjekte edilen sahte istemciler bu callback'i
        // hiç kullanmaz, 401-yenile-tekrarla akışı onlar için test kapsamı dışı.
        if let concreteClient = apiClient as? APIClient {
            concreteClient.refreshHandler = { @MainActor [weak self] in
                await self?.refreshTokens()
            }
        }
        restoreSession()
    }

    // MARK: - Session Restore

    private func restoreSession() {
        guard let token = KeychainStore.load() else { return }
        // We don't have the user's email in Keychain — derive from App Group or use placeholder.
        // The user will see their real email after the next API call.
        let userID = AppGroupStore.loadUserID() ?? 0
        user = AuthUser(id: userID, email: "", token: token)
        Logger.auth.info("Session restored: userID=\(userID)")

        // `validAccessToken()` zaten süre dolumunu PROAKTİF kontrol ediyor —
        // burası (init/restore) kontrol ETMİYORDU, bu yüzden uygulama arka
        // plandan uzun süre sonra öne geldiğinde kullanıcı kısa bir an
        // `HomeView`'i görüp sonra geri sıçrayabiliyordu (M35 audit bulgusu).
        // Senkron init içinden `await` edilemez — bu yüzden en kötü ihtimalle
        // ilk API çağrısının kendi 401→refresh yoluyla düzelteceği durumu,
        // arka planda PROAKTİF bir refresh başlatarak hızlandırıyoruz. Bu,
        // `refreshTokens()`'ın kendi tekilleştirilmiş (serialized) yolundan
        // geçer — ilk ekranın eşzamanlı istekleriyle YARIŞMAZ, aynı devam eden
        // refresh'i paylaşır.
        if JWT.isExpired(token) {
            Logger.auth.info("Restored access token already expired — refreshing proactively")
            Task { await refreshTokens() }
        }
    }

    // MARK: - Login

    @MainActor
    func login(email: String, password: String) async throws {
        isLoading = true
        defer { isLoading = false }

        let response: AuthResponse = try await apiClient.send(
            .login(email: email, password: password),
            token: nil
        )
        persist(response: response)
    }

    // MARK: - Register

    @MainActor
    func register(email: String, password: String, username: String?) async throws {
        isLoading = true
        defer { isLoading = false }

        let response: AuthResponse = try await apiClient.send(
            .register(email: email, password: password, username: username),
            token: nil
        )
        persist(response: response)
    }

    // MARK: - Logout

    @MainActor
    func logout() {
        // `performRefresh()`'in bu epoch'u yakaladığı andan sonra logout
        // çağrılırsa, refresh sunucudan BAŞARIYLA dönse bile artık geçersiz
        // sayılır (M39 audit bulgusu) — bkz. performRefresh().
        sessionEpoch += 1

        // Sunucu tarafında da refresh token'ı iptal et — best-effort, UI'ı bloklamaz.
        if let refreshToken = KeychainStore.loadRefresh() {
            Task {
                let _: StatusResponse? = try? await apiClient.send(.logout(refreshToken: refreshToken), token: nil)
            }
        }
        user = nil
        KeychainStore.delete()
        KeychainStore.deleteRefresh()
        AppGroupStore.clearAll()
        Logger.auth.info("User logged out")
    }

    // MARK: - Token Refresh

    /// Yükleme gibi 401-yenile-tekrarla sarmalayıcısından geçmeyen istekler için
    /// kullanılacak access token'ı döner; süresi dolmak üzereyse önce yeniler.
    ///
    /// `APIClient.send` 401'i yakalayıp isteği tekrarlayabiliyor ama
    /// `uploadVideoFile` ondan geçmiyor — üstelik onlarca MB'lık bir gövdeyi
    /// 401 alıp yeniden göndermek istemeyiz. Bu yüzden proaktif kontrol.
    @MainActor
    func validAccessToken() async -> String? {
        guard let token = user?.token else { return nil }
        guard JWT.isExpired(token) else { return token }

        Logger.auth.info("Access token expiring soon — refreshing before request")
        return await refreshTokens()
    }

    /// Aynı anda devam eden TEK bir refresh çağrısı — `refreshTokens()`'ın
    /// birden fazla eşzamanlı çağırıcısı (ör. TripDetailView'ın üç paralel
    /// `.task`'ı, hepsi aynı anda 401 alırsa) AYNI Task'ı paylaşır, HER BİRİ
    /// KENDİ `/auth/refresh` isteğini ateşlemez. Bu olmadan: iki eşzamanlı
    /// çağrı aynı (henüz rotate edilmemiş) refresh token'ı okur, biri
    /// başarıyla yeni bir çift kalıcı hale getirir, diğeri ise artık geçersiz
    /// olan AYNI eski token'ı kullanmaya çalışıp reddedilir — ve o reddedilme
    /// koşulsuz `handleUnauthorized()`/logout tetikleyip, BİRAZ ÖNCE başarıyla
    /// yenilenmiş GEÇERLİ oturumu siler (M35 audit bulgusu — core-api'nin
    /// `REFRESH_TOKEN_RACE_LOST` kodu tam da bu senaryoyu öngörüyor, bkz.
    /// mobile-bff error_wrapper.py). Tekilleştirme bu yarışı YAPISAL olarak
    /// ortadan kaldırır — bu istemciden ASLA iki eşzamanlı refresh isteği
    /// çıkmaz.
    private var inFlightRefresh: Task<String?, Never>?

    /// `logout()` tarafından artırılır — `performRefresh()`'in başladığı andaki
    /// değeri yakalayıp sonunda karşılaştırması için (bkz. aşağısı).
    private var sessionEpoch = 0

    /// 401 alındığında APIClient tarafından çağrılır — refresh token ile yeni
    /// bir access token almayı dener. Başarısızsa oturumu tamamen kapatır.
    @MainActor
    private func refreshTokens() async -> String? {
        if let inFlightRefresh {
            return await inFlightRefresh.value
        }
        let task = Task<String?, Never> { [weak self] in
            await self?.performRefresh()
        }
        inFlightRefresh = task
        let result = await task.value
        inFlightRefresh = nil
        return result
    }

    @MainActor
    private func performRefresh() async -> String? {
        // Bu refresh'in SONUCU, kullanıcı bu await sırasında logout olduysa
        // artık geçerli değildir — sunucu tarafında yeni bir token çifti
        // gerçekten oluşmuş olsa bile, bunu yerel oturuma UYGULAMAK
        // logout'u sessizce geri alır (M39 audit bulgusu: az önce
        // `KeychainStore.delete()` ile temizlenen oturum, gecikmiş bir
        // refresh yanıtıyla yeniden dirilirdi). `sessionEpoch` bunu YAPISAL
        // olarak imkânsız kılar — `inFlightRefresh` ile AYNI tekilleştirme
        // ilkesi, farklı bir yarış koşulu için.
        let epochAtStart = sessionEpoch
        guard let refreshToken = KeychainStore.loadRefresh() else {
            handleUnauthorized()
            return nil
        }
        do {
            let response: AuthResponse = try await apiClient.send(
                .refresh(refreshToken: refreshToken),
                token: nil
            )
            guard sessionEpoch == epochAtStart else {
                Logger.auth.info("Refresh completed after logout — discarding result")
                return nil
            }
            persist(response: response)
            Logger.auth.info("Access token refreshed")
            return response.accessToken
        } catch {
            guard sessionEpoch == epochAtStart else { return nil }
            Logger.auth.error("Token refresh failed: \(error.localizedDescription)")
            handleUnauthorized()
            return nil
        }
    }

    // MARK: - Apple Sign In

    @MainActor
    func appleSignIn(result: Result<ASAuthorization, Error>) async throws {
        // Kullanıcı sistem sayfasını iptal ederse `result` `.failure(ASAuthorizationError.canceled)`
        // olur — bu BAŞARISIZLIK değil, normal/beklenen bir kullanıcı eylemi.
        // Düzeltme öncesi bu, `guard`in `else` dalına düşüp "Apple ile giriş
        // başarısız." gösteriyordu — Google'ın kendi `GoogleSignInCoordinator.
        // CoordinatorError.cancelled`ının AYNI ekranda ürettiği "Google girişi
        // iptal edildi." ile tutarsız (M36 audit bulgusu): aynı kullanıcı
        // eylemi (iptal), iki OAuth düğmesi arasında farklı, biri yanıltıcı
        // şekilde alarm verici davranıyordu.
        if case .failure(let error) = result,
           let authError = error as? ASAuthorizationError,
           authError.code == .canceled {
            throw APIError.server(code: "APPLE_AUTH_CANCELLED", message: "Apple girişi iptal edildi.")
        }

        guard
            case .success(let auth) = result,
            let credential = auth.credential as? ASAuthorizationAppleIDCredential,
            let tokenData  = credential.identityToken,
            let tokenStr   = String(data: tokenData, encoding: .utf8)
        else {
            throw APIError.server(code: "APPLE_AUTH_FAILED", message: "Apple ile giriş başarısız.")
        }

        let givenName  = credential.fullName?.givenName
        let familyName = credential.fullName?.familyName
        let fullName: String? = [givenName, familyName]
            .compactMap { $0 }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespaces)
            .nilIfEmpty

        isLoading = true
        defer { isLoading = false }

        let response: AuthResponse = try await apiClient.send(
            .appleSignIn(identityToken: tokenStr, fullName: fullName),
            token: nil
        )
        persist(response: response)
    }

    // MARK: - Google Sign In

    /// `ASWebAuthenticationSession`'ın döndürdüğü callback URL'sinden çıkarılan
    /// `code`/`redirectUri` çiftini core-api'ye iletir — `appleSignIn`'le AYNI
    /// akış (kod→token değişimi, client_secret DAHİL, yalnızca core-api'de
    /// yapılır; bu istemci yalnızca tek kullanımlık authorization code'u taşır).
    @MainActor
    func googleSignIn(code: String, redirectUri: String) async throws {
        isLoading = true
        defer { isLoading = false }

        let response: AuthResponse = try await apiClient.send(
            .googleSignIn(code: code, redirectUri: redirectUri),
            token: nil
        )
        persist(response: response)
    }

    // MARK: - Forgot / Reset Password

    /// Sunucu hesap var/yok fark etmeksizin her zaman aynı genel yanıtı
    /// döner (kullanıcı numaralandırmayı önlemek için) — bu yüzden burada
    /// başarı/başarısızlık ayrımı YAPILMAZ, çağıran (ViewModel) her zaman
    /// aynı genel mesajı gösterir.
    @MainActor
    func forgotPassword(email: String) async throws {
        let _: StatusResponse = try await apiClient.send(.forgotPassword(email: email), token: nil)
    }

    @MainActor
    func resetPassword(token: String, newPassword: String) async throws {
        let _: StatusResponse = try await apiClient.send(
            .resetPassword(token: token, newPassword: newPassword),
            token: nil
        )
    }

    // MARK: - Handle 401

    @MainActor
    func handleUnauthorized() {
        logout()
    }

    // MARK: - Private

    private func persist(response: AuthResponse) {
        let authUser = AuthUser(id: response.userId, email: response.email, token: response.accessToken)
        user = authUser
        KeychainStore.save(response.accessToken)
        KeychainStore.saveRefresh(response.refreshToken)
        AppGroupStore.saveToken(response.accessToken)
        AppGroupStore.saveRefreshToken(response.refreshToken)
        AppGroupStore.saveUserID(response.userId)
        Logger.auth.info("Session persisted: userID=\(response.userId)")
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

// MARK: - Test Support

#if DEBUG
extension AuthEnvironment {
    /// Yalnızca testler için: Keychain/session restore akışını atlayıp
    /// doğrudan bir kullanıcı enjekte eder. `user` `private(set)` olduğu için
    /// bu, aynı dosyadaki tek erişim noktası — üretim kodu hiç çağırmaz.
    func setUserForTesting(_ user: AuthUser) {
        self.user = user
    }
}
#endif
