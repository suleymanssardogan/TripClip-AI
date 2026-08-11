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

    // MARK: - Delete (Milestone 19 — Delete Saved Itinerary from History)

    /// Şu an silinmekte olan itinerary'nin id'si — `nil` iken hiçbir silme
    /// isteği sürmüyor demektir. `deleteTrip`in kendi `isDeleting: Bool`
    /// desenindeki AYNI mantık, yalnızca HANGİ satırın meşgul olduğunu da
    /// taşıyabilmesi için `Int?`e genişletildi (bkz. `TripDetailViewModel.isDeleting`) —
    /// satır bazlı yükleme göstergesi VE tek-uçuşta-tek-istek (re-entrancy)
    /// koruması aynı property'den gelir.
    private(set) var deletingID: Int?
    var deleteError: String?

    /// Gerçek bir backend silme isteği — lokal/sahte bir kaldırma DEĞİL
    /// (bkz. spesifikasyonun "must be a real backend deletion" gereksinimi).
    /// Başarılıysa `itineraries`'ten TEK bu öğeyi çıkarır (ekranı yeniden
    /// yüklemeden — Req "do not unnecessarily reload the entire screen if
    /// local removal is sufficient"), sıralama otomatik olarak korunur çünkü
    /// dizinin geri kalanına dokunulmuyor. Başarısızsa öğe listede KALIR ve
    /// `deleteError` set edilir — çağıran View bunu göstermekten sorumlu.
    @discardableResult
    func deleteItinerary(id: Int, auth: AuthEnvironment) async -> Bool {
        // Re-entrancy guard: aynı anda yalnızca bir silme isteği sürebilir —
        // bir satıra art arda/çift dokunmak ikinci bir isteği TETİKLEMEZ.
        guard deletingID == nil else { return false }
        guard let token = auth.user?.token else { return false }
        deletingID = id
        defer { deletingID = nil }

        do {
            let _: SuccessResponse = try await auth.apiClient.send(
                .deleteItinerary(itineraryID: id), token: token
            )
            itineraries.removeAll { $0.id == id }
            return true
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
            deleteError = apiError.localizedDescription
            Logger.network.warning("Itinerary delete failed: \(apiError.localizedDescription)")
            return false
        } catch {
            deleteError = "Silinemedi."
            return false
        }
    }
}
