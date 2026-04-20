import Foundation
import Combine
import AuthenticationServices
import Security

@MainActor
class AuthService: ObservableObject {
    static let shared = AuthService()

    @Published var isAuthenticated = false
    @Published var currentUserId: Int?

    private let baseURL = "http://127.0.0.1:8001/api/mobile"
    private let tokenKey = "tripclip_access_token"
    private let userIdKey = "tripclip_user_id"

    init() {
        loadStoredSession()
    }

    // MARK: - Token Storage (Keychain)

    var accessToken: String? {
        get { keychainGet(tokenKey) }
        set {
            if let val = newValue { keychainSet(tokenKey, value: val) }
            else { keychainDelete(tokenKey) }
        }
    }

    private func loadStoredSession() {
        if let token = accessToken, !token.isEmpty {
            currentUserId = UserDefaults.standard.integer(forKey: userIdKey)
            isAuthenticated = true
        }
    }

    // MARK: - Apple Sign In

    func handleAppleSignIn(result: Result<ASAuthorization, Error>) async throws {
        guard case .success(let auth) = result,
              let credential = auth.credential as? ASAuthorizationAppleIDCredential,
              let tokenData = credential.identityToken,
              let identityToken = String(data: tokenData, encoding: .utf8)
        else {
            throw URLError(.userAuthenticationRequired)
        }

        let fullName: String? = {
            guard let given = credential.fullName?.givenName else { return nil }
            let family = credential.fullName?.familyName ?? ""
            return "\(given) \(family)".trimmingCharacters(in: .whitespaces)
        }()

        let body: [String: Any?] = ["identity_token": identityToken, "full_name": fullName]
        let response = try await post("/auth/apple", body: body.compactMapValues { $0 })
        saveSession(response)
    }

    // MARK: - Email/Password (test için)

    func login(email: String, password: String) async throws {
        let response = try await post("/auth/login", body: ["email": email, "password": password])
        saveSession(response)
    }

    func register(email: String, password: String, username: String?) async throws {
        var body: [String: Any] = ["email": email, "password": password]
        if let u = username { body["username"] = u }
        let response = try await post("/auth/register", body: body)
        saveSession(response)
    }

    // MARK: - Logout

    func logout() {
        accessToken = nil
        UserDefaults.standard.removeObject(forKey: userIdKey)
        isAuthenticated = false
        currentUserId = nil
    }

    // MARK: - Helpers

    private func saveSession(_ data: [String: Any]) {
        guard let token = data["access_token"] as? String,
              let userId = data["user_id"] as? Int else { return }
        accessToken = token
        currentUserId = userId
        UserDefaults.standard.set(userId, forKey: userIdKey)
        isAuthenticated = true
    }

    private func post(_ path: String, body: [String: Any]) async throws -> [String: Any] {
        var request = URLRequest(url: URL(string: baseURL + path)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode < 400 else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw NSError(domain: "Auth", code: 0, userInfo: [NSLocalizedDescriptionKey: detail ?? "Auth failed"])
        }
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    // MARK: - Keychain

    private func keychainGet(_ key: String) -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func keychainSet(_ key: String, value: String) {
        let data = value.data(using: .utf8)!
        let query: [CFString: Any] = [kSecClass: kSecClassGenericPassword, kSecAttrAccount: key]
        if SecItemCopyMatching(query as CFDictionary, nil) == errSecSuccess {
            SecItemUpdate(query as CFDictionary, [kSecValueData: data] as CFDictionary)
        } else {
            var add = query
            add[kSecValueData] = data
            SecItemAdd(add as CFDictionary, nil)
        }
    }

    private func keychainDelete(_ key: String) {
        let query: [CFString: Any] = [kSecClass: kSecClassGenericPassword, kSecAttrAccount: key]
        SecItemDelete(query as CFDictionary)
    }
}
