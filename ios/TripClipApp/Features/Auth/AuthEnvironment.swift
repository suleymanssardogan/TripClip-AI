import SwiftUI
import AuthenticationServices
import OSLog

// MARK: - AuthEnvironment

@Observable
final class AuthEnvironment {

    // MARK: Published State

    private(set) var user:   AuthUser?
    private(set) var isLoading = false

    var isAuthenticated: Bool { user != nil }

    // MARK: Dependencies

    let apiClient: APIClient

    // MARK: Init

    init(apiClient: APIClient = APIClient()) {
        self.apiClient = apiClient
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
        user = nil
        KeychainStore.delete()
        AppGroupStore.clearAll()
        Logger.auth.info("User logged out")
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
        AppGroupStore.saveToken(response.accessToken)
        AppGroupStore.saveUserID(response.userId)
        Logger.auth.info("Session persisted: userID=\(response.userId)")
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}
