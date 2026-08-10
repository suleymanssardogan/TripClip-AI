import Foundation
import CoreLocation
@testable import TripClipApp

/// `OptimizerRoutingProviding` test double. `MKRoute`'un public bir
/// initializer'ı yok (Apple'ın kendisi dışında üretilemiyor), bu yüzden
/// gerçek MapKit tiplerini taklit etmek yerine bu protokolün kendisini
/// taklit ediyoruz — bkz. `OptimizerRouteCalculator.swift`'teki
/// `OptimizerRoutingProviding` doc yorumu.
final class FakeOptimizerRoutingProvider: OptimizerRoutingProviding, @unchecked Sendable {

    struct Call {
        let from: CLLocationCoordinate2D
        let to:   CLLocationCoordinate2D
    }

    private(set) var calls: [Call] = []
    var callCount: Int { calls.count }

    /// Varsayılan: her istek başarıyla `[from, to]` düz çizgisini "rota"
    /// olarak döner — testler bunu gerçekçi bir eğri ya da bir hatayla
    /// (`.failure`) değiştirebilir.
    var resultProvider: (CLLocationCoordinate2D, CLLocationCoordinate2D) -> Result<[CLLocationCoordinate2D], Error> = { from, to in
        .success([from, to])
    }

    /// Verilirse, `route(from:to:)` bu kapı açılana kadar askıda kalır —
    /// "isLoading true iken tekrar çağrılırsa ne olur" gibi ara-durum
    /// testleri için (bkz. `AsyncGate`, `FakeAPIClient.swift`).
    var gate: AsyncGate?

    func route(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D) async throws -> [CLLocationCoordinate2D] {
        calls.append(Call(from: from, to: to))
        if let gate { await gate.wait() }
        switch resultProvider(from, to) {
        case .success(let coords): return coords
        case .failure(let error):  throw error
        }
    }
}

enum FakeRoutingError: Error { case simulatedFailure }
