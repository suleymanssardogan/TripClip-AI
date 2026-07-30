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
}

/// Module-level alias so `APIClient` can use `Config.apiBaseURL` naturally.
typealias Config = TripClipConfig
