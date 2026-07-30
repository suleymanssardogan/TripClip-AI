import Foundation
import Security
import OSLog

// Keychain wrapper — stores a single JWT token.
// All operations are synchronous; Keychain is not async-safe.
enum KeychainStore {

    private static let service        = "com.sardogan.TripClipAI"
    private static let account        = "auth.token"
    private static let refreshAccount = "auth.refreshToken"
    private static let log            = Logger(subsystem: "com.sardogan.TripClipAI", category: "keychain")

    private static func write(_ value: String, account: String) {
        let data = Data(value.utf8)
        let query: [CFString: Any] = [
            kSecClass:       kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecValueData:   data,
        ]
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        if status != errSecSuccess {
            log.error("Keychain save failed (\(account)): \(status)")
        }
    }

    private static func read(account: String) -> String? {
        let query: [CFString: Any] = [
            kSecClass:            kSecClassGenericPassword,
            kSecAttrService:      service,
            kSecAttrAccount:      account,
            kSecReturnData:       true,
            kSecMatchLimit:       kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private static func remove(account: String) {
        let query: [CFString: Any] = [
            kSecClass:       kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Access Token

    static func save(_ token: String)  { write(token, account: account) }
    static func load() -> String?      { read(account: account) }
    static func delete()               { remove(account: account) }

    // MARK: - Refresh Token

    static func saveRefresh(_ token: String) { write(token, account: refreshAccount) }
    static func loadRefresh() -> String?     { read(account: refreshAccount) }
    static func deleteRefresh()              { remove(account: refreshAccount) }
}
