import Foundation
import MapKit

// MARK: - Routing provider seam

/// İki koordinat arasında gerçek yol geometrisi isteyen soyutlama —
/// `OptimizerRouteCalculator`'ın tek MapKit bağımlılığı bu protokol
/// üzerinden akar. `MKRoute`'un public bir initializer'ı yok (Apple bunu
/// yalnızca `MKDirections`'ın kendisi üretebiliyor), bu da onu doğrudan
/// sahte/test verisiyle üretmeyi imkânsız kılıyor — bu yüzden test tarafı
/// `MKRoute` DEĞİL, bu protokolün kendisini taklit ediyor (bkz.
/// `TripClipAppTests/Support/FakeOptimizerRoutingProvider.swift`,
/// docs/ios-trip-optimizer.md "MapKit Directions mimarisi").
protocol OptimizerRoutingProviding {
    func route(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D) async throws -> [CLLocationCoordinate2D]
}

enum OptimizerRoutingError: Error {
    case noRouteFound
}

/// Gerçek `MKDirections` tabanlı sağlayıcı — üretimde kullanılan tek
/// somut implementasyon. Sürüş rotası istiyoruz (Req 1: "driving route
/// geometry"); yürüyüş/toplu taşıma seçenekleri bu milestone'un kapsamı
/// dışında.
struct MKDirectionsRoutingProvider: OptimizerRoutingProviding {
    func route(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D) async throws -> [CLLocationCoordinate2D] {
        let request = MKDirections.Request()
        request.source        = MKMapItem(placemark: MKPlacemark(coordinate: from))
        request.destination   = MKMapItem(placemark: MKPlacemark(coordinate: to))
        request.transportType = .automobile

        let response = try await MKDirections(request: request).calculate()
        guard let route = response.routes.first else { throw OptimizerRoutingError.noRouteFound }
        return route.polyline.coordinates
    }
}

private extension MKPolyline {
    var coordinates: [CLLocationCoordinate2D] {
        var coords = [CLLocationCoordinate2D](repeating: kCLLocationCoordinate2DInvalid, count: pointCount)
        getCoordinates(&coords, range: NSRange(location: 0, length: pointCount))
        return coords
    }
}

// MARK: - Per-day route state

/// Bir güne ait, ardışık durak çiftleri arasındaki tek bir bacak — ya
/// gerçek `MKDirections` yol geometrisi (`isRoaded == true`) ya da o bacak
/// için rota hesaplanamadığında düz-çizgi fallback (`isRoaded == false`,
/// Req 3). `OptimizerRouteMap` iki durumu farklı çizgi stiliyle çizer
/// (bkz. o dosyadaki `isRoaded` kullanımı) — fallback durumu sessizce
/// gizlenmiyor, ama engelleyici bir uyarı da değil.
struct OptimizerRouteSegment {
    let coordinates: [CLLocationCoordinate2D]
    let isRoaded:    Bool
}

/// Bir günün TAMAMI için hesaplanmış rota durumu — `OptimizerRouteMap`'in
/// çizdiği şey budur.
struct OptimizerDayRoute {
    let segments:  [OptimizerRouteSegment]
    let isLoading: Bool
}

/// `OptimizerRouteMapData`'nın (saf/MapKit'siz) günlere ayrılmış durak
/// listesinden yola çıkarak, her gün için ardışık durak çiftleri arasında
/// gerçek sürüş rotası isteyen, sonuçları önbelleğe alan, iptal eden ve
/// eski (stale) yanıtların güncel görünümü asla ezmemesini garanti eden
/// asenkron katman.
///
/// Mimari sınır (Req 4): `OptimizerRouteMapData` bu sınıfı hiç bilmez —
/// hâlâ tamamen saf/MapKit'siz kalıyor. `OptimizerRouteMap` de bu sınıfı
/// bilmez — yalnızca onun ÇIKTISINI (`[Int: OptimizerDayRoute]`, düz bir
/// değer tipi) bir prop olarak alır, kendi hesaplama/iptal mantığı yok.
/// Orkestrasyon tamamen burada, `OptimizerRouteMapSection`'ın sahip olduğu
/// bu tek nesnede yaşıyor.
///
/// MapKit'in `MKDirections`'ı tek bir istekte birden çok durak
/// (waypoint) desteklemiyor — bu yüzden bir günün "Stop1 → Stop2 → Stop3"
/// zinciri, N durak için N-1 ardışık ikili (`from`/`to`) istek olarak
/// hesaplanır; her bacak kendi başarı/başarısızlığını taşır (Req 1, Req 3).
@Observable
@MainActor
final class OptimizerRouteCalculator {

    /// Gün başına en güncel rota durumu — dictionary anahtarı `dayIndex`
    /// olduğundan, bir günün yanıtı YAPISAL olarak başka bir günün
    /// durumunu asla ezemez (Req 5 "a route response for Day 1 must never
    /// overwrite Day 2's currently displayed route").
    private(set) var routes: [Int: OptimizerDayRoute] = [:]

    private let provider: OptimizerRoutingProviding

    /// Tamamlanmış sonuçların önbelleği — anahtar `cacheKey(for:)`, bkz.
    /// aşağıda. Yalnızca bu `OptimizerRouteCalculator` örneğinin ömrü
    /// boyunca yaşar (ekran her açıldığında sıfırdan başlar) — bkz.
    /// docs/ios-trip-optimizer.md "Caching" bölümündeki kapsam kararı.
    private var cache: [String: [OptimizerRouteSegment]] = [:]

    /// Hangi günün hangi anahtar için hâlâ hesaplandığını izler — aynı
    /// gün+sıralama için `load` art arda çağrılsa bile (ör. SwiftUI'nin
    /// tekrarlayan `body` değerlendirmeleri, Req 5/6/9) devam eden isteği
    /// gereksiz yere iptal edip YENİDEN BAŞLATMAMAK için.
    private var inFlightKeys:  [Int: String] = [:]
    private var inFlightTasks: [Int: Task<Void, Never>] = [:]

    init(provider: OptimizerRoutingProviding = MKDirectionsRoutingProvider()) {
        self.provider = provider
    }

    /// Bir stabil önbellek anahtarı üretir: gün + sıralı durak
    /// kimlikleri+koordinatları (Req 6'nın kendi ifadesiyle "day + ordered
    /// stop IDs/coordinates"). Durak sırası değişirse (teorik olarak,
    /// itinerary sabit olduğundan pratikte olmaz) anahtar da değişir —
    /// önbellek yanlışlıkla eski bir sırayı güncel gibi göstermez.
    static func cacheKey(for day: OptimizerMapDay) -> String {
        var parts = ["day=\(day.dayIndex)"]
        parts += day.stops.map { "\($0.id)@\($0.latitude),\($0.longitude)" }
        return parts.joined(separator: "|")
    }

    /// Bir günün rotasını hesaplar/getirir. Aynı gün+sıralama için:
    ///   - önbellekte varsa anında (ağ isteği YOK) döner,
    ///   - zaten hesaplanıyorsa (aynı anahtar in-flight) NO-OP — tekrar
    ///     tetiklenmesi (ör. SwiftUI yeniden render) isteği iptal edip
    ///     yeniden başlatmaz (Req 6, Req 9).
    /// Tek duraklı bir gün için hiç ağ isteği yapılmaz (bacak yok).
    func load(day: OptimizerMapDay) {
        let key = Self.cacheKey(for: day)

        if let cached = cache[key] {
            routes[day.dayIndex] = OptimizerDayRoute(segments: cached, isLoading: false)
            return
        }
        if inFlightKeys[day.dayIndex] == key {
            return   // Aynı gün+sıralama zaten hesaplanıyor — tekrar tetikleme.
        }

        // Bu gün için farklı bir anahtar hesaplanıyorsa (pratikte olmaz,
        // itinerary sabit) onu iptal et; aynı anahtar değilse bu bir
        // no-op'tur.
        inFlightTasks[day.dayIndex]?.cancel()

        guard day.stops.count > 1 else {
            // Tek duraklı gün: bacak yok, hesaplanacak bir şey yok.
            routes[day.dayIndex]     = OptimizerDayRoute(segments: [], isLoading: false)
            inFlightKeys[day.dayIndex]  = nil
            inFlightTasks[day.dayIndex] = nil
            return
        }

        // İstek sürerken de haritanın boş kalmaması için, sonuç gelene
        // kadar düz-çizgi fallback'i hemen göster (Req 3 zaten bunu
        // gerektiriyor; "loading" durumunda da geçerli).
        routes[day.dayIndex] = OptimizerDayRoute(
            segments: Self.straightLineSegments(for: day), isLoading: true
        )
        inFlightKeys[day.dayIndex] = key

        let pairs    = Array(zip(day.stops, day.stops.dropFirst()))
        let provider = self.provider

        let task = Task { [weak self] in
            var segments: [OptimizerRouteSegment] = []
            for (from, to) in pairs {
                if Task.isCancelled { return }
                let fromCoordinate = CLLocationCoordinate2D(latitude: from.latitude, longitude: from.longitude)
                let toCoordinate   = CLLocationCoordinate2D(latitude: to.latitude, longitude: to.longitude)
                do {
                    let coords = try await provider.route(from: fromCoordinate, to: toCoordinate)
                    segments.append(OptimizerRouteSegment(coordinates: coords, isRoaded: true))
                } catch {
                    // Bu bacak için rota hesaplanamadı — crash yok, durak
                    // kaybolmuyor, o bacak düz çizgiye düşüyor (Req 3).
                    segments.append(OptimizerRouteSegment(
                        coordinates: [fromCoordinate, toCoordinate], isRoaded: false
                    ))
                }
            }
            if Task.isCancelled { return }

            guard let self else { return }
            self.cache[key] = segments
            self.routes[day.dayIndex]     = OptimizerDayRoute(segments: segments, isLoading: false)
            if self.inFlightKeys[day.dayIndex] == key {
                self.inFlightKeys[day.dayIndex]  = nil
                self.inFlightTasks[day.dayIndex] = nil
            }
        }
        inFlightTasks[day.dayIndex] = task
    }

    /// Görünümden kaybolurken (Req 5 "view disappearance") tüm bekleyen
    /// hesaplamaları iptal eder — arka planda tamamlanıp artık ekranda
    /// olmayan bir görünümün state'ini boşuna güncellemesini önler.
    func cancelAll() {
        inFlightTasks.values.forEach { $0.cancel() }
        inFlightTasks.removeAll()
        inFlightKeys.removeAll()
    }

    private static func straightLineSegments(for day: OptimizerMapDay) -> [OptimizerRouteSegment] {
        zip(day.stops, day.stops.dropFirst()).map { from, to in
            OptimizerRouteSegment(
                coordinates: [
                    CLLocationCoordinate2D(latitude: from.latitude, longitude: from.longitude),
                    CLLocationCoordinate2D(latitude: to.latitude, longitude: to.longitude),
                ],
                isRoaded: false
            )
        }
    }
}
