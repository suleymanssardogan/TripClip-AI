import Foundation

// App Group UserDefaults — shared between main app and Share Extension.
// The Share Extension reads the auth token from here (can't access Keychain).
enum AppGroupStore {

    private static let groupID = BackgroundUploader.Config.appGroupID

    private static var defaults: UserDefaults? {
        UserDefaults(suiteName: groupID)
    }

    private enum Keys {
        static let authToken     = "authToken"
        static let currentUserID = "currentUserID"
    }

    // MARK: - Auth Token

    static func saveToken(_ token: String) {
        defaults?.set(token, forKey: Keys.authToken)
    }

    static func loadToken() -> String? {
        defaults?.string(forKey: Keys.authToken)
    }

    static func deleteToken() {
        defaults?.removeObject(forKey: Keys.authToken)
    }

    // MARK: - User ID (needed by Share Extension for x-user-id header)

    static func saveUserID(_ id: Int) {
        defaults?.set(id, forKey: Keys.currentUserID)
    }

    static func loadUserID() -> Int? {
        guard let defaults, defaults.object(forKey: Keys.currentUserID) != nil else { return nil }
        let id = defaults.integer(forKey: Keys.currentUserID)
        return id > 0 ? id : nil
    }

    static func deleteUserID() {
        defaults?.removeObject(forKey: Keys.currentUserID)
    }

    // MARK: - Logout (clears all shared data)

    static func clearAll() {
        deleteToken()
        deleteUserID()
    }
}
