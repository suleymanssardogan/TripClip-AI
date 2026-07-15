import Foundation
import OSLog

@Observable
@MainActor
final class HomeViewModel {

    private(set) var plans:     [PlanSummary] = []
    private(set) var isLoading  = false
    private(set) var error: APIError?

    func load(auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let userID = auth.user?.id, let token = auth.user?.token else { return }

        do {
            let response: PlanListResponse = try await auth.apiClient.send(
                .userVideos(userID: userID),
                token: token
            )
            plans = response.plans
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Home load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
