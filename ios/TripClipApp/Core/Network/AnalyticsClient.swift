import Foundation
import OSLog

/// Shared-trip büyüme hunisi event'lerini sunucuya iletir (bkz.
/// docs/analytics/shared-trip-events.md). Her zaman fire-and-forget:
/// başarısız olursa sessizce loglar, hiçbir zaman UI'a yansımaz veya mevcut
/// bir kullanıcı eylemini engellemez.
@MainActor
final class AnalyticsClient {

    static let shared = AnalyticsClient()

    private init() {}

    /// Aynı (event, tripID) çifti bu pencere içinde tekrar ateşlenmez —
    /// yanlışlıkla çift dokunma ya da SwiftUI'nin bir eylemi iki kez
    /// tetiklemesi ihtimaline karşı. ResultsViewModel.stopWriteCooldown ile
    /// aynı gerekçe, çok daha kısa ömürlü bir eylem için.
    private static let duplicateWindow: Duration = .seconds(2)
    private var lastFiredAt: [String: ContinuousClock.Instant] = [:]

    func track(_ event: String, tripID: Int, source: String, auth: AuthEnvironment) {
        let key = "\(event):\(tripID)"
        let now = ContinuousClock.now
        if let last = lastFiredAt[key], now - last < Self.duplicateWindow {
            return
        }
        lastFiredAt[key] = now

        guard let token = auth.user?.token else { return }

        Task {
            do {
                let _: SuccessResponse = try await auth.apiClient.send(
                    .trackAnalyticsEvent(event: event, tripID: tripID, source: source),
                    token: token
                )
            } catch {
                // Best-effort — kullanıcıya asla gösterilmez, yalnızca teşhis için loglanır.
                Logger.network.debug("Analytics event gönderilemedi (best-effort): \(String(describing: error))")
            }
        }
    }
}
