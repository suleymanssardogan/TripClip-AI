/// AppDelegate+BackgroundSession.swift — TripClip Ana Uygulama
///
/// iOS, Share Extension'ın background URLSession'ı tamamlandığında
/// ana uygulamayı uyandırır ve bu metodu çağırır.
///
/// Uygulama bu noktada:
///   1. Session'ı aynı ID ile yeniden oluşturur (iOS bunu bekler)
///   2. App Group'tan pending video ID'sini okur
///   3. İlgili ekrana navigate eder veya bildirim gönderir

import UIKit

extension AppDelegate {

    /// Ana uygulama Xcode projesindeki AppDelegate'e bu metodu ekleyin.
    ///
    /// ```swift
    /// func application(_ application: UIApplication,
    ///   handleEventsForBackgroundURLSession identifier: String,
    ///   completionHandler: @escaping () -> Void) {
    ///     handleBackgroundSession(identifier: identifier,
    ///                             completionHandler: completionHandler)
    /// }
    /// ```
    func handleBackgroundSession(identifier: String,
                                 completionHandler: @escaping () -> Void) {
        guard identifier == BackgroundUploader.Config.sessionID else {
            completionHandler()
            return
        }

        // 1. Session'ı yeniden oluştur — iOS pending event'leri bu delegate'e iletir
        //    BackgroundUploader.shared.backgroundSession erişimi lazy init'i tetikler
        _ = BackgroundUploader.shared

        // 2. Tüm eventler teslim edilince iOS completion handler'ı ister
        NotificationCenter.default.addObserver(
            forName: .tripClipBackgroundUploadFinished,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            completionHandler()
            self?.handlePendingVideoIfNeeded()
        }
    }

    // MARK: - Pending Video

    /// App Group'ta bekleyen video ID'si varsa ilgili ekrana yönlendir.
    func handlePendingVideoIfNeeded() {
        guard let videoID = BackgroundUploader.shared.consumePendingVideoID() else { return }

        // Bildirim gönder — RootViewController veya SwiftUI NavigationState dinleyebilir
        NotificationCenter.default.post(
            name: .tripClipNavigateToVideo,
            object: videoID
        )
    }
}

extension Notification.Name {
    static let tripClipNavigateToVideo = Notification.Name(
        "com.sardogan.TripClipAI.navigateToVideo"
    )
}
