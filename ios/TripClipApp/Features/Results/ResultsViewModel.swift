import Foundation
import OSLog

@Observable
@MainActor
final class ResultsViewModel {

    private(set) var plan:      PlanDetail?
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    /// İpuçları ertelenmiş task'ta üretildiği için sonuç ekranı açıldığında
    /// henüz hazır olmayabilir. Bu durumda kısa aralıklarla yeniden sorgularız.
    private(set) var isWaitingForTips = false
    private(set) var tipsUnavailable  = false

    private var tipsPollingTask: Task<Void, Never>?

    /// Toplam ~30 saniye bekler (10 × 3s). Ölçümde ipuçları completed'dan
    /// ~7 saniye sonra düşüyor; Gemini kota (429) yediğinde hiç gelmiyor,
    /// bu yüzden sonsuz döngü yok — sınırdan sonra vazgeçip mesaj gösteriyoruz.
    private static let tipsPollAttempts = 10
    private static let tipsPollInterval: Duration = .seconds(3)

    func load(planID: Int, auth: AuthEnvironment, preloaded: PlanDetail? = nil) async {
        // Serve from offline cache immediately if available
        if let preloaded {
            plan = preloaded
            startTipsPollingIfNeeded(planID: planID, auth: auth)
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
            startTipsPollingIfNeeded(planID: planID, auth: auth)
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

    // MARK: - Ertelenmiş İpuçları

    /// Ekrandan çıkıldığında yoklamayı durdurur (bkz. ResultsView.onDisappear).
    /// `deinit` içinde yapılamıyor: deinit nonisolated, bu tip @MainActor.
    func stopTipsPolling() {
        tipsPollingTask?.cancel()
        tipsPollingTask = nil
    }

    /// Plan tamamlanmış ama ipuçları henüz boşsa arka planda yoklamaya başlar.
    private func startTipsPollingIfNeeded(planID: Int, auth: AuthEnvironment) {
        guard let plan, plan.status.lowercased() == "completed" else { return }
        guard plan.travelTips.isEmpty else {
            isWaitingForTips = false
            tipsUnavailable  = false
            return
        }
        guard tipsPollingTask == nil else { return }   // zaten yokluyoruz

        isWaitingForTips = true
        tipsUnavailable  = false

        tipsPollingTask = Task { [weak self] in
            defer { self?.tipsPollingTask = nil }

            for _ in 0..<Self.tipsPollAttempts {
                try? await Task.sleep(for: Self.tipsPollInterval)
                if Task.isCancelled { return }
                guard let self, let token = auth.user?.token else { return }

                let detail: PlanDetail? = try? await auth.apiClient.send(
                    .videoDetail(videoID: planID), token: token
                )
                guard let detail else { continue }

                if !detail.travelTips.isEmpty {
                    self.plan = detail
                    self.isWaitingForTips = false
                    PersistenceController.shared.save(planDetail: detail)
                    Logger.network.info("Results: tips arrived for plan \(planID)")
                    return
                }
            }

            // Süre doldu — ipuçları gelmedi (ör. Gemini kotası).
            self?.isWaitingForTips = false
            self?.tipsUnavailable  = true
            Logger.network.info("Results: tips did not arrive for plan \(planID)")
        }
    }
}
