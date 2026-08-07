import Foundation
import OSLog

@Observable
@MainActor
final class TripsListViewModel {

    private(set) var trips:     [TripSummary] = []
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    func load(auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let response: TripListResponse = try await auth.apiClient.send(.tripList, token: token)
            trips = response.trips
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Trip list load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
