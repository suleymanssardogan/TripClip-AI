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

    func optimize(tripID: Int, placeIDs: [Int], auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(
                .optimizeTrip(tripID: tripID, placeIDs: placeIDs), token: token
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
}
