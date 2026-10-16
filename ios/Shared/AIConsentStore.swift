import Foundation

/// Device-local permission, shared with the extension, scoped to account and disclosure.
enum AIConsentStore {
    static let key = "aiSharingConsent"
    static var signature: String { "v1|\(TripClipConfig.apiBaseURL)|\(TripClipConfig.aiProviderName)" }
    static var defaults: UserDefaults? { UserDefaults(suiteName: BackgroundUploader.Config.appGroupID) }

    static func hasConsent(userID: Int, in storage: UserDefaults? = defaults) -> Bool {
        guard userID > 0, let record = storage?.dictionary(forKey: key) else { return false }
        return record["userID"] as? Int == userID && record["signature"] as? String == signature
    }

    @discardableResult
    static func grant(userID: Int, in storage: UserDefaults? = defaults) -> Bool {
        guard userID > 0, let storage else { return false }
        storage.set(["userID": userID, "signature": signature], forKey: key)
        return hasConsent(userID: userID, in: storage)
    }

    static func revoke(in storage: UserDefaults? = defaults) {
        storage?.removeObject(forKey: key)
    }

    static var disclosure: String {
        "Video veya paylaştığın bağlantı TripClip sunucusuna gönderilir. Analiz için görüntü kareleri, çıkarılan metinler ve gezi asistanına yazdığın mesajlar \(TripClipConfig.aiProviderName) ile paylaşılabilir. Bu bilgiler kişisel veri içerebilir. Yalnızca paylaşmaya hakkın olan içerikleri gönder. İzin vermeden kayıtlı gezilerini görüntüleyebilirsin. İzni Gizlilik ekranından geri alabilirsin; bu, daha önce gönderilen verileri silmez."
    }
}
