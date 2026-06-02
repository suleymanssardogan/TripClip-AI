/// BackgroundUploader.swift — TripClip Share Extension
///
/// İki sorumluluğu var:
///   1. App Group UserDefaults üzerinden ana uygulama ile veri paylaşımı
///   2. URLSessionConfiguration.background ile API'ye URL gönderimi
///
/// Neden background session?
///   - Share Extension süreci kısa ömürlüdür; iOS istediği zaman kill edebilir.
///   - URLSessionConfiguration.background ile oluşturulan görevler iOS'un
///     networking subsystem'inde yaşar; extension process ölse bile devam eder.
///   - Görev tamamlandığında iOS ana uygulamayı uyandırır ve AppDelegate'deki
///     handleEventsForBackgroundURLSession metodu çağrılır.

import Foundation

// MARK: - BackgroundUploader

final class BackgroundUploader: NSObject {

    // MARK: Singleton

    static let shared = BackgroundUploader()
    private override init() { super.init() }

    // MARK: Configuration

    /// Tüm projeye özel değerler — Bundle ID ile eşleşmeli.
    enum Config {
        static let appGroupID   = "group.com.seninbundleid"           // App Group
        static let sessionID    = "com.seninbundleid.shareextension.bgupload"
        static let apiBaseURL   = "https://api.tripclip.app"          // Production URL
    }

    // MARK: App Group Keys

    private enum Keys {
        static let authToken      = "authToken"          // Ana uygulama yazar, extension okur
        static let pendingURL     = "pendingURL"          // Gönderilmek üzere bekleyen URL
        static let pendingVideoID = "pendingVideoID"      // API'den dönen video ID'si
        static let lastUploadDate = "lastUploadDate"
    }

    // MARK: App Group UserDefaults

    private var sharedDefaults: UserDefaults {
        // Bu çağrı başarısız olursa App Group Entitlement eksiktir.
        // Xcode → Signing & Capabilities → App Groups → group.com.seninbundleid
        UserDefaults(suiteName: Config.appGroupID)!
    }

    // MARK: - App Group Read / Write

    /// Extension'dan okur; ana uygulamanın JWT'sini kullanır.
    var authToken: String? {
        sharedDefaults.string(forKey: Keys.authToken)
    }

    /// Ana uygulamanın yazmak için kullandığı setter.
    func storeAuthToken(_ token: String) {
        sharedDefaults.set(token, forKey: Keys.authToken)
    }

    /// Gönderilecek URL'i App Group'a yazar.
    /// - Ana uygulama çevrimdışıyken extension kapatıldığında URL kaybolmaz.
    func storePendingURL(_ url: URL) {
        sharedDefaults.set(url.absoluteString, forKey: Keys.pendingURL)
        sharedDefaults.set(Date(), forKey: Keys.lastUploadDate)
    }

    /// API'nin döndürdüğü video ID'sini yazar; ana uygulama bunu okuyarak
    /// progress polling başlatır.
    func storePendingVideoID(_ id: Int) {
        sharedDefaults.set(id, forKey: Keys.pendingVideoID)
    }

    /// Ana uygulama açıldığında çağırmalı — işlenmiş video varsa ID'yi döner
    /// ve kaydı temizler.
    func consumePendingVideoID() -> Int? {
        let id = sharedDefaults.integer(forKey: Keys.pendingVideoID)
        guard id > 0 else { return nil }
        sharedDefaults.removeObject(forKey: Keys.pendingVideoID)
        sharedDefaults.removeObject(forKey: Keys.pendingURL)
        return id
    }

    // MARK: - Background URLSession

    /// `sharedContainerIdentifier` ayarlandığı için extension process kapansa bile
    /// iOS bu session'ı yaşatır ve tamamlandığında ana uygulamayı uyandırır.
    private lazy var backgroundSession: URLSession = {
        var config = URLSessionConfiguration.background(withIdentifier: Config.sessionID)
        config.sharedContainerIdentifier = Config.appGroupID // ← kritik
        config.isDiscretionary           = false             // hemen başlat
        config.sessionSendsLaunchEvents  = true              // ana uygulamayı uyandır
        config.timeoutIntervalForRequest  = 30
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    // MARK: - Public API

    typealias EnqueueCompletion = (Result<Void, UploaderError>) -> Void

    /// URL'i App Group'a yazar ve arka planda API'ye POST eder.
    ///
    /// - Parameter url: Doğrulanmış Instagram URL'i.
    /// - Parameter userID: JWT'den alınan kullanıcı ID'si.
    /// - Parameter completion: Görev kuyruğa alındığında (202 beklenmez) çağrılır.
    ///
    /// ⚠️ Bu metod `extensionContext.completeRequest`'in completion handler'ı
    ///    içinden çağrılmalıdır. Extension process'i henüz canlıyken
    ///    URLSession task'i başlatmak zorundayız.
    func enqueue(url: URL,
                 userID: Int,
                 completion: @escaping EnqueueCompletion) {

        guard let token = authToken else {
            completion(.failure(.notAuthenticated))
            return
        }

        storePendingURL(url)

        // Request
        guard let endpoint = URL(string: "\(Config.apiBaseURL)/api/mobile/videos/queue-url") else {
            completion(.failure(.invalidConfiguration))
            return
        }
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json",    forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)",     forHTTPHeaderField: "Authorization")
        request.setValue(String(userID),        forHTTPHeaderField: "X-User-ID")

        // JSON body
        let body: [String: Any] = [
            "url":    url.absoluteString,
            "source": "instagram_share_extension"
        ]

        // Background upload task — httpBody değil temp dosyası gerektirir.
        guard
            let bodyData = try? JSONSerialization.data(withJSONObject: body),
            let tempFile  = writeTempFile(data: bodyData)
        else {
            completion(.failure(.encodingFailed))
            return
        }

        let task = backgroundSession.uploadTask(with: request, fromFile: tempFile)
        task.taskDescription = url.absoluteString   // delegate'de tanımak için
        task.resume()

        completion(.success(()))
    }

    // MARK: - Temp File Helper

    /// Shared container'a JSON dosyası yazar.
    /// Background task için httpBody yerine dosya yolu gereklidir.
    private func writeTempFile(data: Data) -> URL? {
        let dir = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: Config.appGroupID
        ) ?? FileManager.default.temporaryDirectory

        let file = dir.appendingPathComponent("tc_share_\(UUID().uuidString).json")
        do {
            try data.write(to: file, options: .atomic)
            return file
        } catch {
            print("[BackgroundUploader] Temp dosyası yazılamadı: \(error)")
            return nil
        }
    }

    // MARK: - Errors

    enum UploaderError: LocalizedError {
        case notAuthenticated
        case invalidConfiguration
        case encodingFailed

        var errorDescription: String? {
            switch self {
            case .notAuthenticated:    return "Önce TripClip'e giriş yapın."
            case .invalidConfiguration: return "API adresi geçersiz."
            case .encodingFailed:      return "İstek hazırlanamadı."
            }
        }
    }
}

// MARK: - URLSessionDataDelegate

extension BackgroundUploader: URLSessionDataDelegate {

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive data: Data) {
        guard
            let json    = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let videoID = json["id"] as? Int
        else { return }

        // Video ID'yi sakla — ana uygulama polling yapacak
        storePendingVideoID(videoID)
        print("[BackgroundUploader] Video kuyruğa alındı: id=\(videoID)")
    }

    func urlSession(_ session: URLSession,
                    task: URLSessionTask,
                    didCompleteWithError error: Error?) {
        if let error = error {
            // Hata — URL App Group'ta duruyor, ana uygulama retry yapabilir
            print("[BackgroundUploader] Upload başarısız: \(error.localizedDescription)")
        }
        // Temp dosyaları temizle
        cleanupTempFiles()
    }

    /// iOS, arka plan session'ı tamamladığında ana uygulamada
    /// `handleEventsForBackgroundURLSession` tetiklenir.
    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async {
            NotificationCenter.default.post(
                name: .tripClipBackgroundUploadFinished,
                object: session.configuration.identifier
            )
        }
    }

    // MARK: - Cleanup

    private func cleanupTempFiles() {
        guard let dir = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: Config.appGroupID
        ) else { return }

        let files = (try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: nil
        )) ?? []

        files
            .filter { $0.lastPathComponent.hasPrefix("tc_share_") }
            .forEach { try? FileManager.default.removeItem(at: $0) }
    }
}

// MARK: - Notification Name

extension Notification.Name {
    static let tripClipBackgroundUploadFinished = Notification.Name(
        "com.seninbundleid.backgroundUploadFinished"
    )
}
