import Foundation
import OSLog

@Observable
@MainActor
final class ResultsViewModel {

    private(set) var plan:      PlanDetail?
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    func load(planID: Int, auth: AuthEnvironment, preloaded: PlanDetail? = nil) async {
        // Serve from offline cache immediately if available
        if let preloaded {
            plan = preloaded
            return
        }

        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let detail: PlanDetail = try await auth.apiClient.send(
                .videoDetail(videoID: planID), token: token
            )
            plan = detail
            // Auto-save completed plans to CoreData for offline access
            if detail.status.lowercased() == "completed" {
                PersistenceController.shared.save(planDetail: detail)
            }
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            // Try offline cache as fallback
            if let cached = PersistenceController.shared.fetch(id: planID)?.decodedPlanDetail {
                plan = cached
                Logger.network.info("Results: using offline cache for plan \(planID)")
            } else {
                error = apiError
                Logger.network.warning("Results load failed: \(apiError.localizedDescription ?? "")")
            }
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
