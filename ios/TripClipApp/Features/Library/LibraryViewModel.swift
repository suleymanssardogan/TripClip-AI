import Foundation
import OSLog

@Observable
@MainActor
final class LibraryViewModel {

    private(set) var places:    [LibraryPlace] = []
    private(set) var isLoading  = false
    private(set) var error: APIError?

    func load(auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            // Sunucu sayfalama üst sınırı 50 — erken kullanıcılar için tek
            // seferde tamamı yeterli; arama/filtre bu listenin üzerinde
            // istemci tarafında çalışır (bkz. LibraryView.filteredPlaces).
            let response: LibraryResponse = try await auth.apiClient.send(
                .library(city: nil, q: nil, limit: 50, offset: 0),
                token: token
            )
            places = response.places
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Library load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    // MARK: - Trip Builder

    private(set) var isCreatingTrip = false
    var tripCreationError: String?

    /// Seçilen mekanlardan TSP ile rotalanmış yeni bir Trip oluşturur.
    /// Başarılı olursa oluşturulan gezi döner; çağıran taraf bunu Trip Detail'e
    /// navigasyon için kullanır (bkz. LibraryView.createdTrip).
    func createTrip(title: String, placeIDs: [Int], auth: AuthEnvironment) async -> TripDetail? {
        guard !isCreatingTrip, let token = auth.user?.token else { return nil }
        isCreatingTrip = true
        tripCreationError = nil
        defer { isCreatingTrip = false }

        do {
            return try await auth.apiClient.send(
                .createTrip(title: title, placeIDs: placeIDs),
                token: token
            )
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return nil }
            tripCreationError = apiError.localizedDescription
            Logger.network.warning("Trip creation failed: \(apiError.localizedDescription ?? "")")
            return nil
        } catch {
            tripCreationError = "Gezi oluşturulamadı."
            return nil
        }
    }
}
