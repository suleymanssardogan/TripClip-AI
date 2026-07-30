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
import UserNotifications

// MARK: - BackgroundUploader

// @unchecked Sendable: singleton with internal-only mutation; thread safety is
// guaranteed by URLSession's own internal serialization.
final class BackgroundUploader: NSObject, @unchecked Sendable {

    // MARK: Singleton

    static let shared = BackgroundUploader()
    private override init() { super.init() }

    // MARK: Configuration

    /// Bundle IDs — must match provisioning profiles.
    /// API URL is accessed via TripClipConfig.apiBaseURL to avoid name shadowing.
    enum Config {
        static let appGroupID = "group.com.sardogan.TripClipAI"
        static let sessionID  = "com.sardogan.TripClipAI.shareextension.bgupload"
    }

    // MARK: App Group Keys

    private enum Keys {
        static let authToken      = "authToken"          // Ana uygulama yazar, extension okur
        static let refreshToken   = "refreshToken"        // Access token dolduğunda yenilemek için
        static let pendingURL     = "pendingURL"          // Gönderilmek üzere bekleyen URL
        static let pendingVideoID = "pendingVideoID"      // API'den dönen video ID'si
        static let lastUploadDate = "lastUploadDate"
        // Upload başarısız olduğunda (ağ hatası veya sunucu hata status'u) yazılır.
        // Eskiden başarısızlık sadece print() ile logluyordu — extension process
        // zaten kapanmak üzereyken kimse bu logu görmüyordu ve ana uygulamanın
        // başarısızlığı fark etmesinin HİÇBİR yolu yoktu (kullanıcı videoyu
        // paylaşır, hiçbir şey olmaz, sessizce kaybolur).
        static let pendingUploadError = "pendingUploadError"
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

    /// Access token dolduğunda yeni bir tane almak için kullanılır.
    var refreshToken: String? {
        sharedDefaults.string(forKey: Keys.refreshToken)
    }

    // MARK: - Token Tazeleme

    /// Access token'ın süresi dolmak üzereyse refresh token ile yeniler.
    ///
    /// Share Extension `APIClient`'ı kullanmıyor, dolayısıyla onun
    /// 401-yakala-yenile-tekrarla mantığından faydalanamıyor. Ayrıca yenilemenin
    /// `extensionContext.completeRequest`'ten ÖNCE yapılması şart: sonrasında
    /// process suspend ediliyor ve yalnızca başlatılmış background task'lar
    /// hayatta kalıyor, yeni bir ağ isteği yapacak vakit kalmıyor.
    ///
    /// - Returns: Kullanılabilir bir access token; oturum yenilenemiyorsa nil.
    func ensureFreshToken() async -> String? {
        guard let token = authToken else { return nil }
        guard JWT.isExpired(token) else { return token }

        guard
            let refreshToken,
            let endpoint = URL(string: "\(TripClipConfig.apiBaseURL)/api/mobile/auth/refresh")
        else { return nil }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(
            withJSONObject: ["refresh_token": refreshToken]
        )
        request.timeoutInterval = 15

        do {
            // Background session DEĞİL: yanıtı hemen okumamız gerekiyor.
            let (data, response) = try await URLSession.shared.data(for: request)
            guard
                (response as? HTTPURLResponse)?.statusCode == 200,
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let newAccess = json["access_token"] as? String
            else { return nil }

            storeAuthToken(newAccess)
            if let newRefresh = json["refresh_token"] as? String {
                sharedDefaults.set(newRefresh, forKey: Keys.refreshToken)
            }
            return newAccess
        } catch {
            print("[BackgroundUploader] Token yenilenemedi: \(error.localizedDescription)")
            return nil
        }
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

    /// Upload başarısız olduysa hata mesajını yazar — ana uygulama bunu okuyup
    /// kullanıcıya gösterebilir (bkz. AppDelegate+BackgroundSession.swift).
    func storePendingUploadError(_ message: String) {
        sharedDefaults.set(message, forKey: Keys.pendingUploadError)
    }

    /// Ana uygulama açıldığında/uyandığında çağırmalı — bekleyen bir upload
    /// hatası varsa mesajı döner ve kaydı temizler (tek seferlik tüketim,
    /// consumePendingVideoID ile aynı desen).
    func consumePendingUploadError() -> String? {
        guard let message = sharedDefaults.string(forKey: Keys.pendingUploadError) else { return nil }
        sharedDefaults.removeObject(forKey: Keys.pendingUploadError)
        sharedDefaults.removeObject(forKey: Keys.pendingURL)
        return message
    }

    // MARK: - Background URLSession

    private lazy var backgroundSession: URLSession = {
        #if targetEnvironment(simulator)
        // Background URLSession'ın delegate callback'leri (didCompleteWithError,
        // urlSessionDidFinishEvents) Simulator'da güvenilir şekilde tetiklenmiyor —
        // background session'ın tüm amacı (extension process ölse bile devam etmek)
        // zaten Simulator'da anlamsız. Test edilebilirlik için normal (foreground)
        // bir session kullanıyoruz; gerçek cihazda hâlâ background session kullanılır.
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest  = 30
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
        #else
        var config = URLSessionConfiguration.background(withIdentifier: Config.sessionID)
        config.sharedContainerIdentifier = Config.appGroupID
        config.isDiscretionary           = false
        config.sessionSendsLaunchEvents  = true
        config.timeoutIntervalForRequest  = 30
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
        #endif
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
        guard let endpoint = URL(string: "\(TripClipConfig.apiBaseURL)/api/mobile/videos/queue-url") else {
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
        // Ağ hatası (error != nil) VEYA sunucu hata status'u (401/429/500 vb.) —
        // ikisi de kullanıcının videosunun kuyruğa alınamadığı anlamına gelir.
        // Eskiden yalnızca error != nil kontrol ediliyordu; bir 4xx/5xx yanıtı
        // (task tamamlanır, error nil) sessizce hiçbir iz bırakmadan kaybolurdu.
        let httpStatus = (task.response as? HTTPURLResponse)?.statusCode
        let failed = error != nil || !(200...299).contains(httpStatus ?? 200)

        if failed {
            let message = error?.localizedDescription
                ?? "Sunucu hatası (\(httpStatus.map(String.init) ?? "bilinmeyen"))"
            print("[BackgroundUploader] Upload başarısız: \(message)")
            storePendingUploadError(message)
            notifyUploadFailed(message: message)
        }
        // Temp dosyaları temizle
        cleanupTempFiles()
    }

    /// Best-effort local bildirim — kullanıcı uygulamayı hiç açmasa bile
    /// paylaşımın başarısız olduğunu fark etsin diye. Bildirim izni yoksa
    /// (kullanıcı reddetmiş) sessizce hiçbir şey olmaz.
    private func notifyUploadFailed(message: String) {
        let content = UNMutableNotificationContent()
        content.title = "Video paylaşılamadı"
        content.body  = message
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: "tripclip-upload-failed-\(UUID().uuidString)",
            content: content,
            trigger: nil   // hemen göster
        )
        UNUserNotificationCenter.current().add(request)
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
