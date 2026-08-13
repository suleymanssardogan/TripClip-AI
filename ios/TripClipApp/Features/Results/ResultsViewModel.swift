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

    // MARK: - Durak Düzenleme

    /// Sunucuya sıra yazılırken true — düzenleme arayüzü kilitlenir.
    private(set) var isSavingStops = false
    /// Kaydetme başarısızsa kullanıcıya gösterilecek mesaj.
    var stopEditError: String?

    /// Son kaydın bittiği an. Tek bir dokunuşun iki kez tetiklendiği ölçüldü
    /// (aynı taşıma için 64 ms arayla iki istek). Silme idempotent olduğu için
    /// zararsızdı ama taşıma iki kez uygulanıp sırayı sessizce bozuyordu —
    /// kullanıcı ne olduğunu göremediği için en kötü hata türü.
    private var lastStopWriteAt: ContinuousClock.Instant?
    /// İnsanın kasıtlı olarak iki kez basamayacağı kadar kısa bir pencere;
    /// gerçek ardışık dokunuşlar (300 ms+) etkilenmiyor.
    private static let stopWriteCooldown: Duration = .milliseconds(250)

    /// Durağı listeden çıkarır ve kalan sırayı sunucuya yazar.
    ///
    /// Silme ve sıralama aynı alanda (`stop_order`) taşınıyor: gönderdiğimiz
    /// listede olmayan durak silinmiş sayılır. Bu yüzden id olarak
    /// `LocationPin.index` gider — ekranda görünen sıra numarası değil, o
    /// dizi pozisyonundan üretilir.
    func deleteStop(_ pin: LocationPin, auth: AuthEnvironment) async {
        guard let current = plan else { return }
        var remaining = current.locations
        remaining.removeAll { $0.index == pin.index }
        await persistStops(remaining, auth: auth)
    }

    /// Sürükle-bırak ile yeni sırayı uygular ve sunucuya yazar.
    func moveStops(from source: IndexSet, to destination: Int, auth: AuthEnvironment) async {
        guard let current = plan else { return }
        var reordered = current.locations
        reordered.move(fromOffsets: source, toOffset: destination)
        await persistStops(reordered, auth: auth)
    }

    /// Yerel state'i iyimser günceller, sonra sunucuya yazar; hata olursa geri alır.
    private func persistStops(_ locations: [LocationPin], auth: AuthEnvironment) async {
        guard var current = plan, let token = auth.user?.token else { return }
        guard !isSavingStops else { return }
        // Yazma sırasında gelen kopya isteği yukarıdaki guard yakalıyor; istek
        // 30 ms'de bitince guard'ın penceresi kapanıyor, bu yüzden bitiş
        // sonrasını da kısa bir süre koruyoruz.
        if let last = lastStopWriteAt,
           ContinuousClock.now - last < Self.stopWriteCooldown {
            return
        }

        let snapshot = current
        current.locations = locations
        // Rota çizgisi de kullanıcının sırasını izlemeli, yoksa liste bir şey
        // çizgi başka bir şey gösterir. Sunucu da bir sonraki okumada aynısını
        // üretiyor (mobile-bff _route_from_locations).
        current.route = locations.count > 1
            ? locations.map { RoutePoint(latitude: $0.latitude, longitude: $0.longitude, name: $0.name) }
            : nil
        plan = current

        isSavingStops = true
        defer {
            isSavingStops  = false
            lastStopWriteAt = ContinuousClock.now
        }

        do {
            let _: SuccessResponse = try await auth.apiClient.send(
                .updateStopOrder(videoID: current.id, order: [locations.map(\.index)]),
                token: token
            )
            PersistenceController.shared.save(planDetail: current)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            plan = snapshot
            stopEditError = apiError.localizedDescription
            Logger.network.warning("Stop order save failed: \(apiError.localizedDescription)")
        } catch {
            plan = snapshot
            stopEditError = "Değişiklik kaydedilemedi."
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

                let detail: PlanDetail?
                do {
                    detail = try await auth.apiClient.send(.videoDetail(videoID: planID), token: token)
                } catch let apiError as APIError where apiError.isUnauthorized {
                    // `preloaded:` ile açılan bir ResultsView'da (bkz. HistoryView)
                    // `load()` hiç ağa gitmez — bu yoklama o durumda TEK gerçek
                    // istek olabilir. Önceden `try?` her hatayı (401 dahil)
                    // sessizce yutup döngüye devam ediyordu — oturum GERÇEKTEN
                    // sona ermişken bile (M37 audit bulgusu, diğer tüm
                    // authenticated çağrıların zaten yaptığı kontrol eksikti).
                    // `defer` zaten `tipsPollingTask`ı temizleyecek.
                    auth.handleUnauthorized()
                    return
                } catch {
                    detail = nil
                }
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
