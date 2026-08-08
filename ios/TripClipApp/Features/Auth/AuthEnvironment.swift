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

    /// 401 alındığında APIClient tarafından çağrılır — refresh token ile yeni
    /// bir access token almayı dener. Başarısızsa oturumu tamamen kapatır.
    @MainActor
    private func refreshTokens() async -> String? {
        guard let refreshToken = KeychainStore.loadRefresh() else {
            handleUnauthorized()
            return nil
        }
        do {
            let response: AuthResponse = try await apiClient.send(
                .refresh(refreshToken: refreshToken),
                token: nil
            )
            persist(response: response)
            Logger.auth.info("Access token refreshed")
            return response.accessToken
        } catch {
            Logger.auth.error("Token refresh failed: \(error.localizedDescription)")
            handleUnauthorized()
            return nil
        }
    }

    // MARK: - Apple Sign In

    @MainActor
    func appleSignIn(result: Result<ASAuthorization, Error>) async throws {
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
