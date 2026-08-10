import Foundation
import OSLog

/// AI Trip Optimizer — ya mevcut bir Trip'in duraklarından YENİ bir itinerary
/// önizlemesi üretir (`optimize`), ya da daha önce üretilmiş, kaydedilmiş bir
/// itinerary'i olduğu gibi yükler (`loadItinerary`) — Itinerary History'den
/// açıldığında optimizer TEKRAR ÇALIŞTIRILMAZ, yalnızca kayıtlı sonuç
/// görüntülenir (bkz. docs/ios-trip-optimizer.md "Itinerary History").
///
/// İkisi de aynı `run` yardımcısını paylaşır (tek fark: hangi Endpoint'in
/// çağrıldığı) — TripDetailViewModel.load ile birebir aynı desen (re-entrancy
/// guard, is-loading/error çifti, 401'de auth.handleUnauthorized).
@Observable
@MainActor
final class TripOptimizerViewModel {

    private(set) var itinerary: Itinerary?
    private(set) var isLoading = false
    private(set) var error:    APIError?

    func optimize(tripID: Int, placeIDs: [Int], durationDays: Int? = nil, auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(
                .optimizeTrip(tripID: tripID, placeIDs: placeIDs, durationDays: durationDays), token: token
            )
        }
    }

    func loadItinerary(itineraryID: Int, auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(
                .itineraryDetail(itineraryID: itineraryID), token: token
            )
        }
    }

    private func run(auth: AuthEnvironment, request: (String) async throws -> Itinerary) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            itinerary = try await request(token)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Trip optimizer request failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    // MARK: - Trip'e Uygula — bkz. docs/trip-optimizer.md "Apply semantics"
    //
    // Kayıtlı itinerary'i Trip'in kanonik TripStop listesine yazar. `itinerary`
    // (görüntülenen önizleme) BİLEREK dokunulmadan kalır — apply saved
    // itinerary'i mutasyona uğratmaz, yalnızca Trip'i günceller (Req 11).
    // deleteTrip ile aynı desen: re-entrancy guard, @discardableResult -> Bool.

    private(set) var isApplying = false
    var applyError: String?

    @discardableResult
    func applyToTrip(itineraryID: Int, auth: AuthEnvironment) async -> Bool {
        guard !isApplying, let token = auth.user?.token else { return false }
        isApplying = true
        applyError = nil
        defer { isApplying = false }

        do {
            let _: ApplyItineraryResult = try await auth.apiClient.send(
                .applyItinerary(itineraryID: itineraryID), token: token
            )
            return true
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
            applyError = apiError.localizedDescription
            Logger.network.warning("Apply itinerary failed: \(apiError.localizedDescription ?? "")")
            return false
        } catch {
            applyError = "Itinerary uygulanamadı."
            return false
        }
    }
}
