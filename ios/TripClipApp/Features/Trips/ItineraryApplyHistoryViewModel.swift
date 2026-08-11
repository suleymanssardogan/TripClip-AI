import Foundation
import OSLog

/// AI Trip Optimizer — bir Trip'e uygulanan (ve geri alınan) HER değişikliğin
/// kalıcı geçmişi. `ItineraryHistoryViewModel` ile AYNI iskelet (re-entrancy
/// guard, is-loading/error çifti, 401'de auth.handleUnauthorized) — ayrı bir
/// ekran/kaynak olduğu için (itinerary'lerin KENDİ listesi değil, bir trip'e
/// ne zaman/ne uygulandığının günlüğü) ayrı bir ViewModel, ama
/// `TripOptimizerViewModel`e YENİ, ilgisiz bir sorumluluk YÜKLENMEDİ (bkz.
/// docs/ios-trip-optimizer.md "Apply History & Undo").
@Observable
@MainActor
final class ItineraryApplyHistoryViewModel {

    private(set) var entries:   [ApplyHistoryEntry] = []
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    func load(tripID: Int, auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let response: ApplyHistoryListResponse = try await auth.apiClient.send(
                .applyHistory(tripID: tripID), token: token
            )
            entries = response.entries
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Apply history load failed: \(apiError.localizedDescription)")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    // MARK: - Undo

    /// Şu an geri alınmakta olan kaydın id'si — re-entrancy guard VE
    /// hangi satırın meşgul olduğunu taşıyan tek property (bkz.
    /// `ItineraryHistoryViewModel.deletingID`'nin AYNI deseni).
    private(set) var undoingID: Int?
    var undoError: String?

    /// Sunucu tek otorite (Req "Do not locally guess the restored state.
    /// The server is authoritative") — başarılı bir undo `entries`'i LOKAL
    /// olarak yamamaz: bir undo yalnızca TEK satırı değil, hem hedef
    /// kaydın `isUndoable` bayrağını hem de YENİ bir kaydın kendisini
    /// etkiler. Bu yüzden bu metot BİLEREK yalnızca undo isteğinin
    /// kendisini yapar — yeniden yükleme sorumluluğu çağırana (View) bırakılır
    /// (`ItineraryApplyHistoryView`, başarıdan SONRA ayrıca `load()` çağırır).
    /// Bu, hem `deleteItinerary`'nin "tek metot = tek ağ çağrısı" desenini
    /// korur hem de bu metodu tek başına, deterministik olarak test
    /// edilebilir kılar (`FakeAPIClient` tek seferde tek bir tipli sonuç
    /// taşır — undo+reload'ı TEK metotta birleştirmek bunu test edilemez
    /// kılardı).
    @discardableResult
    func undo(historyID: Int, tripID: Int, auth: AuthEnvironment) async -> Bool {
        guard undoingID == nil else { return false }
        guard let token = auth.user?.token else { return false }
        undoingID = historyID
        defer { undoingID = nil }

        do {
            let _: UndoApplyResult = try await auth.apiClient.send(
                .undoApplyHistory(tripID: tripID, historyID: historyID), token: token
            )
            return true
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
            undoError = apiError.localizedDescription
            Logger.network.warning("Undo apply history failed: \(apiError.localizedDescription)")
            return false
        } catch {
            undoError = "Geri alınamadı."
            return false
        }
    }
}
