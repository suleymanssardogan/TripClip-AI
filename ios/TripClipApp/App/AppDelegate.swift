import UIKit
import OSLog
import UserNotifications

final class AppDelegate: NSObject, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        requestNotificationPermission()
        return true
    }

    // MARK: - Push Notifications

    private func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if granted {
                DispatchQueue.main.async {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
            if let error {
                Logger.upload.warning("Notification permission error: \(error.localizedDescription)")
            }
        }
        UNUserNotificationCenter.current().delegate = self
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Logger.upload.info("APNs token: \(token)")
        UserDefaults.standard.set(token, forKey: "apns_device_token")
        sendDeviceTokenToBackend(token)
    }

    // Girişli kullanıcı yoksa (KeychainStore.load() nil) gönderim atlanır —
    // login sonrası AuthEnvironment burayı tekrar tetiklemez, ama token zaten
    // UserDefaults'ta saklı; bir sonraki app-relaunch + APNs re-registration'da
    // (veya bu metod login akışından da çağrılırsa) gönderilir.
    private func sendDeviceTokenToBackend(_ token: String) {
        guard let accessToken = KeychainStore.load() else { return }
        Task {
            do {
                let _: StatusResponse = try await APIClient().send(
                    .registerDeviceToken(token: token),
                    token: accessToken
                )
                Logger.upload.info("APNs token registered with backend")
            } catch {
                Logger.upload.warning("APNs token registration failed: \(error.localizedDescription)")
            }
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        Logger.upload.warning("APNs registration failed: \(error.localizedDescription)")
    }

    // Called when iOS wakes the app for a completed background URLSession.
    // Defined in AppDelegate+BackgroundSession.swift.
    func application(
        _ application: UIApplication,
        handleEventsForBackgroundURLSession identifier: String,
        completionHandler: @escaping () -> Void
    ) {
        Logger.upload.info("Background session event: \(identifier)")
        handleBackgroundSession(identifier: identifier, completionHandler: completionHandler)
    }

    // Soğuk başlatma ve arka plandan öne dönüş — ikisini de kapsar. Share
    // Extension bir video/hata bıraktığında ana uygulama her zaman
    // handleEventsForBackgroundURLSession ile uyanmıyor (örn. kullanıcı
    // extension'dan sonra uygulamayı elle açarsa); bu yüzden aynı tüketim
    // burada da tetiklenir. didFinishLaunching'te değil burada yapılıyor —
    // SwiftUI view hiyerarşisi (HomeView'ın .onReceive'ı) bu noktada zaten
    // kurulu, aksi halde post edilen bildirim kaybolurdu.
    func applicationDidBecomeActive(_ application: UIApplication) {
        handlePendingVideoIfNeeded()
        handlePendingUploadErrorIfNeeded()
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension AppDelegate: @preconcurrency UNUserNotificationCenterDelegate {

    // Called when a notification arrives while the app is in the foreground.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    // Called when the user taps a notification.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        if let videoIDStr = userInfo["video_id"] as? String,
           let videoID    = Int(videoIDStr) {
            NotificationCenter.default.post(name: .tripClipNavigateToVideo, object: videoID)
        }
        completionHandler()
    }
}
