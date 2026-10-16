import Foundation
import OSLog

@Observable
@MainActor
final class TripsListViewModel {

    private(set) var trips:     [TripSummary] = []
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    private(set) var hasMore = false
    private var nextOffset = 0

    func loadMore(auth: AuthEnvironment) async {
        guard hasMore else { return }
        await load(auth: auth, append: true)
    }

    func load(auth: AuthEnvironment, append: Bool = false) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let response: TripListResponse = try await auth.apiClient.send(append ? .tripPage(limit: 20, offset: nextOffset) : .tripList, token: token)
            let start = append ? nextOffset : 0
            if append {
                let existing = Set(trips.map(\.id))
                trips.append(contentsOf: response.trips.filter { !existing.contains($0.id) })
            } else {
                trips = response.trips
            }
            nextOffset = start + response.trips.count
            hasMore = !response.trips.isEmpty && (response.hasMore ?? (nextOffset < (response.total ?? nextOffset)))
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Trip list load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
