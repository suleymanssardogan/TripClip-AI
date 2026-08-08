import Foundation
import OSLog

/// AI Trip Optimizer — mevcut bir Trip'in duraklarından tek seferlik bir
/// itinerary önizlemesi üretir. TripDetailViewModel.load ile birebir aynı
/// desen (tek async giriş noktası, is<X>ing + error çifti, 401'de
/// auth.handleUnauthorized) — bkz. docs/ios-trip-optimizer.md "ViewModel".
@Observable
@MainActor
final class TripOptimizerViewModel {

    private(set) var itinerary: Itinerary?
    private(set) var isLoading = false
    private(set) var error:    APIError?

    func optimize(tripID: Int, placeIDs: [Int], auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            itinerary = try await auth.apiClient.send(
                .optimizeTrip(tripID: tripID, placeIDs: placeIDs), token: token
            )
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Trip optimize failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
