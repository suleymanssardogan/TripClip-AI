import Foundation
import OSLog

@Observable
@MainActor
final class HomeViewModel {

    private(set) var plans:     [PlanSummary] = []
    private(set) var isLoading  = false
    private(set) var error: APIError?
    /// `load()`'ın `error`'ından KASITLI OLARAK AYRI — `HomeView`'in gövdesi
    /// `vm.error` varsa TÜM listeyi tam ekran bir hata durumuyla değiştiriyordu;
    /// `deletePlan` de AYNI `error`'ı kullansaydı, tek bir başarısız silme
    /// (ör. geçici bir ağ sorunu) kullanıcının TÜM gezi listesini kaybetmiş
    /// gibi görünmesine yol açardı (M36 audit bulgusu). Sibling ekranlarla
    /// (`ItineraryHistoryView.deleteError`, `TripDetailViewModel.stopEditError`)
    /// AYNI desen: ayrı bir alan, `.alert` ile gösterilir, liste YERİNDE kalır.
    var deleteError: String?

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

        guard let userID = auth.user?.id, let token = auth.user?.token else { return }

        do {
            let response: PlanListResponse = try await auth.apiClient.send(
                .userVideos(userID: userID, limit: 20, offset: append ? nextOffset : 0),
                token: token
            )
            let start = append ? nextOffset : 0
            if append {
                let existing = Set(plans.map(\.id))
                plans.append(contentsOf: response.plans.filter { !existing.contains($0.id) })
            } else {
                plans = response.plans
            }
            nextOffset = start + response.plans.count
            hasMore = !response.plans.isEmpty && (response.hasMore ?? (nextOffset < response.total))
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Home load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    /// Planı sunucudan ve yerel önbellekten siler.
    ///
    /// Listeden iyimser olarak çıkarıyoruz — silme başarısız olursa geri
    /// koyuyoruz, böylece kullanıcı ne sahte bir başarı görüyor ne de
    /// dokunduktan sonra saniyelerce bekliyor.
    func deletePlan(_ plan: PlanSummary, auth: AuthEnvironment) async {
        guard let token = auth.user?.token else { return }

        let snapshot = plans
        plans.removeAll { $0.id == plan.id }

        do {
            let _: SuccessResponse = try await auth.apiClient.send(
                .deletePlan(videoID: plan.id), token: token
            )
            nextOffset = max(0, nextOffset - 1)
            if let cached = PersistenceController.shared.fetch(id: plan.id) {
                PersistenceController.shared.delete(cached)
            }
            Logger.network.info("Plan deleted: \(plan.id)")
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            plans = snapshot
            deleteError = apiError.localizedDescription
            Logger.network.warning("Plan delete failed: \(apiError.localizedDescription)")
        } catch {
            plans = snapshot
            deleteError = "Plan silinemedi."
        }
    }
}

// MARK: - Test Support

#if DEBUG
extension HomeViewModel {
    /// Yalnızca testler için: `plans` `private(set)` olduğu için bu, aynı
    /// dosyadaki tek erişim noktası — `AuthEnvironment.setUserForTesting`
    /// ile AYNI desen.
    func setPlansForTesting(_ plans: [PlanSummary]) {
        self.plans = plans
    }
}
#endif
