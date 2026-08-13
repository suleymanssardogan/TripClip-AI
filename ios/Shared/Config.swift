import Foundation

/// Central API configuration for both app targets.
/// `TripClipConfig` avoids name collisions with `BackgroundUploader.Config`.
enum TripClipConfig {

    #if DEBUG
    /// Fiziksel cihazda test ederken "localhost" telefonun kendisini işaret eder,
    /// Mac'i değil. `DEV_API_HOST` build setting'i (project.yml → Debug config)
    /// Mac'in LAN IP'sine ayarlanmalı; Simulator'da "localhost" hâlâ çalışır çünkü
    /// Simulator, host'un ağ yığınını paylaşır.
    static let apiBaseURL: String = {
        guard
            let host = Bundle.main.infoDictionary?["DEV_API_HOST"] as? String,
            !host.isEmpty, host != "$(DEV_API_HOST)"
        else {
            return "http://localhost:8001"
        }
        return "http://\(host):8001"
    }()
    #else
    static let apiBaseURL: String = "https://api.tripclip.app"
    #endif

    static var apiBaseAsURL: URL {
        URL(string: apiBaseURL)!
    }

    /// Google OAuth client_id — YALNIZCA genel, gizli DEĞİL (bkz.
    /// GOOGLE_CLIENT_SECRET, yalnızca core-api'de). Boş/tanımsızsa Google
    /// Sign-In devre dışı kalır (bkz. WelcomeView, isGoogleSignInConfigured).
    static var googleClientID: String? {
        guard
            let value = Bundle.main.infoDictionary?["GOOGLE_CLIENT_ID"] as? String,
            !value.isEmpty, value != "$(GOOGLE_CLIENT_ID)"
        else { return nil }
        return value
    }

    /// Google'ın rıza ekranından sonra geri döneceği custom URL scheme —
    /// bundle identifier'ın KENDİSİ (bkz. GOOGLE_ALLOWED_REDIRECT_URIS,
    /// core-api'nin kendi allowlist'i). `ASWebAuthenticationSession` bu
    /// şemayı Info.plist'te KAYITLI bir URL Type olmadan da yakalayabilir —
    /// callback'i kendi ephemeral oturumu içinde intercept eder.
    static let googleRedirectURI = "\(Bundle.main.bundleIdentifier ?? "com.sardogan.TripClipAI"):/oauth2redirect"
}

/// Module-level alias so `APIClient` can use `Config.apiBaseURL` naturally.
typealias Config = TripClipConfig
