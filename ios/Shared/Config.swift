import Foundation

/// Central API configuration for both app targets.
/// `TripClipConfig` avoids name collisions with `BackgroundUploader.Config`.
enum TripClipConfig {

    #if DEBUG
    static let apiBaseURL: String = "http://localhost:8001"
    #else
    static let apiBaseURL: String = "https://api.tripclip.app"
    #endif

    static var apiBaseAsURL: URL {
        URL(string: apiBaseURL)!
    }
}

/// Module-level alias so `APIClient` can use `Config.apiBaseURL` naturally.
typealias Config = TripClipConfig
