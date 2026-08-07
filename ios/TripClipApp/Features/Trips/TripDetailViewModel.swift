import Foundation
import OSLog

@Observable
@MainActor
final class TripDetailViewModel {

    private(set) var trip:      TripDetail?
    private(set) var isLoading  = false
    private(set) var error:     APIError?

    func load(tripID: Int, auth: AuthEnvironment, preloaded: TripDetail? = nil) async {
        if let preloaded {
            trip = preloaded
            return
        }

        guard !isLoading else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            trip = try await auth.apiClient.send(.tripDetail(tripID: tripID), token: token)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
            Logger.network.warning("Trip load failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    // MARK: - Durak Düzenleme
    //
    // Trip Builder şu an oluşturma anında tüm durakları tek güne (days[0])
    // koyuyor (bkz. sql_trip_repository.create_trip) — bu yüzden düzenleme de
    // o tek gün üzerinde çalışıyor. Video editor'ündeki (ResultsViewModel)
    // aynı desen: silme/sıralama tek `order` isteğiyle taşınır.

    private(set) var isSavingStops = false
    var stopEditError: String?

    func deleteStop(_ stop: TripStop, auth: AuthEnvironment) async {
        guard let current = trip, var day = current.days.first else { return }
        day.removeAll { $0.placeId == stop.placeId }
        await persistDay(day, auth: auth)
    }

    func moveStops(from source: IndexSet, to destination: Int, auth: AuthEnvironment) async {
        guard let current = trip, var day = current.days.first else { return }
        day.move(fromOffsets: source, toOffset: destination)
        await persistDay(day, auth: auth)
    }

    private func persistDay(_ day: [TripStop], auth: AuthEnvironment) async {
        guard var current = trip, let token = auth.user?.token else { return }
        guard !isSavingStops else { return }

        let snapshot = current
        current.days = day.isEmpty ? [] : [day]
        trip = current

        isSavingStops = true
        defer { isSavingStops = false }

        do {
            let _: SuccessResponse = try await auth.apiClient.send(
                .updateTripStopOrder(tripID: current.id, order: day.isEmpty ? [] : [day.map(\.placeId)]),
                token: token
            )
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            trip = snapshot
            stopEditError = apiError.localizedDescription
            Logger.network.warning("Trip stop order save failed: \(apiError.localizedDescription ?? "")")
        } catch {
            trip = snapshot
            stopEditError = "Değişiklik kaydedilemedi."
        }
    }

    // MARK: - Silme

    private(set) var isDeleting = false
    var deleteError: String?

    /// Başarılıysa true — çağıran taraf ekranı kapatır.
    func deleteTrip(auth: AuthEnvironment) async -> Bool {
        guard let trip, let token = auth.user?.token else { return false }
        guard !isDeleting else { return false }
        isDeleting = true
        defer { isDeleting = false }

        do {
            let _: SuccessResponse = try await auth.apiClient.send(
                .deleteTrip(tripID: trip.id), token: token
            )
            return true
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
            deleteError = apiError.localizedDescription
            return false
        } catch {
            deleteError = "Gezi silinemedi."
            return false
        }
    }
}
