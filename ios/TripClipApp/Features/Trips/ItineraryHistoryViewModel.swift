import Foundation
import OSLog

/// AI Trip Optimizer — bir Trip için şimdiye kadar üretilmiş itinerary'lerin
/// listesi. TripsListViewModel.load ile birebir aynı desen (re-entrancy guard,
/// is-loading/error çifti, 401'de auth.handleUnauthorized) — bkz.
/// docs/ios-trip-optimizer.md "Itinerary History".
@Observable
@MainActor
final class ItineraryHistoryViewModel {

    private(set) var itineraries: [ItinerarySummary] = []
    private(set) var isLoading    = false
    private(set) var error:       APIError?

    func load(tripID: Int, auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let response: ItineraryListResponse = try await auth.apiClient.send(
                .itineraries(tripID: tripID), token: token
            )
            itineraries = Self.sortedNewestFirst(response.itineraries)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Itinerary history load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    /// core-api zaten created_at DESC döner (bkz. SqlOptimizationRepository.
    /// list_itineraries) — bu ikinci, istemci-taraflı sıralama kasıtlı bir
    /// savunma katmanı: sunucu sözleşmesi ileride değişse bile ekran hep en
    /// yeniden eskiye göstermeli. Ayrıştırılamayan/eksik created_at'ler için
    /// stabil (orijinal sırayı bozmaz) — `internal`, doğrudan test edilebilsin diye.
    static func sortedNewestFirst(_ items: [ItinerarySummary]) -> [ItinerarySummary] {
        items.sorted { a, b in
            guard let dateA = a.createdAt.flatMap(APIDate.parse),
                  let dateB = b.createdAt.flatMap(APIDate.parse) else { return false }
            return dateA > dateB
        }
    }
}
