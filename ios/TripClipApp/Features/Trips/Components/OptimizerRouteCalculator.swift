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
    func route(
        from: CLLocationCoordinate2D, to: CLLocationCoordinate2D, mode: OptimizerTransportMode
    ) async throws -> [CLLocationCoordinate2D]
}

enum OptimizerRoutingError: Error {
    case noRouteFound
}

/// Gerçek `MKDirections` tabanlı sağlayıcı — üretimde kullanılan tek
/// somut implementasyon. Taşıma modu tamamen `mode.mapKitType`'a devredilir
/// — bu tip kendisi `.automobile`/`.walking`/`.transit` arasında hiçbir
/// karar vermez, yalnızca çağıranın seçtiğini `MKDirections.Request`'e
/// yansıtır (bkz. docs/ios-trip-optimizer.md "Optimizer Route Transport
/// Mode", "Transit Transport Mode"). `MKDirectionsTransportType`'ın TEK
/// sızıntı noktası burasıdır — `mode.mapKitType` dışında bu ham tip
/// hiçbir katmana geçmez.
///
/// Transit için `departureDate`/`arrivalDate` BİLEREK ayarlanmıyor —
/// `MKDirections.Request`'in kendi varsayılanı ("şimdi kalkış") kullanılır.
/// Optimizer'ın kendi `planningDate`/`preferredStartTime`/`preferredEndTime`
/// alanları BURAYA hiç akmaz: `OptimizerRoutingProviding.route(from:to:mode:)`
/// imzasının bir zaman parametresi yok, ve onu eklemek `OptimizerRouteCalculator`,
/// `OptimizerRouteCache`'in anahtar biçimi, ve konfigürasyon katmanı
/// arasında yeni bir bağımlılık zinciri açardı — bu tek başına ayrı,
/// gerçek bir "zamanlama farkında toplu taşıma" milestone'u gerektirir
/// (bkz. docs, "Do not turn this into a full public-transit timetable
/// optimizer"). Sonuç: transit rotası hesaplanabildiğinde geçerli bir
/// rota GEOMETRİSİdir, ama optimizer'ın planladığı gün/saatteki gerçek
/// bir sefer için garanti EDİLMEMİŞTİR — yalnızca "şu an kalkılsa" temelli
/// bir tahmindir.
struct MKDirectionsRoutingProvider: OptimizerRoutingProviding {
    func route(
        from: CLLocationCoordinate2D, to: CLLocationCoordinate2D, mode: OptimizerTransportMode
    ) async throws -> [CLLocationCoordinate2D] {
        let request = MKDirections.Request()
        request.source        = MKMapItem(placemark: MKPlacemark(coordinate: from))
        request.destination   = MKMapItem(placemark: MKPlacemark(coordinate: to))
        request.transportType = mode.mapKitType

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

    /// Başarıyla hesaplanmış BACAKLARIN (gün değil — bkz. `legKey`)
    /// önbelleği. Varsayılan: bu `OptimizerRouteCalculator` örneğine özel,
    /// taze bir `OptimizerRouteCache` — testlerin/eski çağıranların hiçbir
    /// şey enjekte etmeden önceki (ekran-ömürlü) davranışı aynen almaya
    /// devam etmesi için. Üretimde `OptimizerRouteMapSection`, `TripClipApp`
    /// düzeyinde bir kez oluşturulup `.environment()` ile enjekte edilen,
    /// EKRAN ÖMRÜNÜ AŞAN paylaşılan örneği geçirir (bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Route Cache").
    private let cache: OptimizerRouteCache

    /// Hangi günün hangi anahtar için hâlâ hesaplandığını izler — aynı
    /// gün+sıralama için `load` art arda çağrılsa bile (ör. SwiftUI'nin
    /// tekrarlayan `body` değerlendirmeleri, Req 5/6/9) devam eden isteği
    /// gereksiz yere iptal edip YENİDEN BAŞLATMAMAK için. Bu takip EKRAN
    /// (calculator örneği) ÖMÜRLÜ kalır — Req 10 "if sharing in-flight work
    /// across screen instances adds unnecessary complexity, it is
    /// acceptable for in-flight tasks to remain screen-scoped."
    private var inFlightKeys:  [Int: String] = [:]
    private var inFlightTasks: [Int: Task<Void, Never>] = [:]

    init(
        provider: OptimizerRoutingProviding = MKDirectionsRoutingProvider(),
        cache: OptimizerRouteCache = OptimizerRouteCache()
    ) {
        self.provider = provider
        self.cache = cache
    }

    /// Bir günün YAPISAL kimliğini üretir: itinerary + gün + taşıma modu +
    /// sıralı durak kimlikleri+koordinatları (Req 6'nın kendi ifadesiyle
    /// "day + ordered stop IDs/coordinates", Req 15 "route identity").
    /// In-flight de-duplication'ın (Req 10) anahtarı budur. `itineraryID`
    /// olmadan iki FARKLI itinerary'nin aynı gün+durak diziliminde bitmesi
    /// teorik olarak mümkün olduğundan (bkz. `OptimizerMapDay.itineraryID`
    /// doc yorumu) o da anahtarın parçası (Req 4 "itinerary isolation").
    /// `mode` — Optimizer Route Transport Mode milestone'unda eklendi —
    /// aynı gün+durak dizilimi için Araba ile Yürüyüş'ün AYNI yapısal
    /// kimliği paylaşmasını önlüyor: mod değişince bu anahtar da değişir,
    /// bu da `load`'ın eski (farklı moddaki) in-flight isteği iptal edip
    /// yeni mod için yeniden başlamasını sağlıyor (bkz. `load` içindeki
    /// "in-flight eşleşmiyor → iptal et, yeniden başla" akışı). `mode`
    /// varsayılanı `.automobile` — bu fonksiyonun eski (mod parametresiz)
    /// çağıranları (testler dahil) davranışını DEĞİŞTİRMEDEN derlenmeye
    /// devam eder.
    /// Durak sırası değişirse (teorik olarak, itinerary sabit olduğundan
    /// pratikte olmaz) anahtar da değişir — önbellek yanlışlıkla eski bir
    /// sırayı güncel gibi göstermez (Req 5).
    static func cacheKey(for day: OptimizerMapDay, mode: OptimizerTransportMode = .automobile) -> String {
        var parts = ["itinerary=\(day.itineraryID)", "day=\(day.dayIndex)", "mode=\(mode.rawValue)"]
        parts += day.stops.map { "\($0.id)@\($0.latitude),\($0.longitude)" }
        return parts.joined(separator: "|")
    }

    /// TEK BİR bacağın (ardışık iki durak arası) kalıcı önbellek anahtarı —
    /// `OptimizerRouteCache`'in granülerliği `cacheKey(for:)`'in GÜN
    /// düzeyinden daha ince: Req 9 "successful legs may be cached; failed
    /// legs must remain retryable; do not cache an entire day as
    /// successful when individual route segments failed" bunu gerektiriyor.
    /// Taşıma modu artık anahtarın PARÇASI (Optimizer Route Transport Mode
    /// milestone'u) — aynı bacak için Araba/Yürüyüş/Toplu Taşıma sonuçları
    /// AYRI, birbirini asla ezmeyen girdiler olarak bir arada yaşar (bkz.
    /// docs/ios-trip-optimizer.md "Cache identity"). `mode.rawValue` KEYFİ
    /// bir string olduğundan bu fonksiyon YENİ bir `OptimizerTransportMode`
    /// case'i eklendiğinde (Transit Transport Mode milestone'unda
    /// doğrulandığı gibi) DEĞİŞMEDEN kalır — yeni case otomatik olarak
    /// kendi bağımsız önbellek ad alanını alır.
    private static func legKey(
        day: OptimizerMapDay, from: OptimizerMapStop, to: OptimizerMapStop, mode: OptimizerTransportMode
    ) -> String {
        "itinerary=\(day.itineraryID)|day=\(day.dayIndex)|mode=\(mode.rawValue)|\(from.id)@\(from.latitude),\(from.longitude)"
            + "->\(to.id)@\(to.latitude),\(to.longitude)"
    }

    /// Bir günün TÜM bacakları, VERİLEN mod için, kalıcı önbellekte ise
    /// sonucu döner — yoksa (kısmen ya da tamamen eksikse) `nil`. Bu, Req
    /// 16'nın "no new loading UI for cache hits... the user should simply
    /// see the route immediately" gereksinimini karşılayan SENKRON hızlı
    /// yoldur: hiçbir `Task` başlatılmaz, hiçbir "loading" durumuna hiç
    /// girilmez.
    private func fullyCachedSegments(
        pairs: [(OptimizerMapStop, OptimizerMapStop)], day: OptimizerMapDay, mode: OptimizerTransportMode
    ) -> [OptimizerRouteSegment]? {
        guard !pairs.isEmpty else { return nil }
        var segments: [OptimizerRouteSegment] = []
        for (from, to) in pairs {
            guard let coordinates = cache.coordinates(for: Self.legKey(day: day, from: from, to: to, mode: mode)) else {
                return nil
            }
            segments.append(OptimizerRouteSegment(coordinates: coordinates, isRoaded: true))
        }
        return segments
    }

    /// Bir günün, VERİLEN taşıma modu için rotasını hesaplar/getirir.
    /// `mode` varsayılanı `.automobile` — mevcut (mod belirtmeyen) tüm
    /// çağıranlar (testler dahil) üretim davranışını hiç değiştirmeden
    /// derlenmeye devam eder (Req 12 "existing callers should continue to
    /// default to automobile").
    ///   - Günün TÜM bacakları bu mod için kalıcı önbellekte ise: SENKRON,
    ///     ağ isteği YOK, "loading" durumu YOK (Req 16).
    ///   - Aynı gün+sıralama+mod zaten hesaplanıyorsa (aynı anahtar
    ///     in-flight): NO-OP — tekrar tetiklenmesi (ör. SwiftUI yeniden
    ///     render) isteği iptal edip yeniden başlatmaz (Req 6, Req 9, Req
    ///     10).
    ///   - Kısmen önbellekteyse: önbellekteki bacaklar için AĞ İSTEĞİ
    ///     YAPILMAZ, yalnızca eksik/önceden başarısız bacaklar için
    ///     `MKDirections`'a başvurulur (Req 8 "a later visit may retry the
    ///     failed route").
    ///   - Mod DEĞİŞTİĞİNDE (aynı gün, farklı `mode`): anahtar farklı
    ///     olduğundan yukarıdaki in-flight eşleşmesi tutmaz — önceki modun
    ///     hâlâ süren isteği (varsa) iptal edilir, o günün gösterilen
    ///     rotası hemen düz-çizgi+"loading" durumuna döner (eski modun
    ///     rotası ekranda asılı KALMAZ), ve yeni mod için hesaplama
    ///     başlar — ya da yeni mod zaten önbellekteyse yukarıdaki senkron
    ///     yoldan anında görünür.
    /// Tek duraklı bir gün için hiç ağ isteği yapılmaz (bacak yok).
    func load(day: OptimizerMapDay, mode: OptimizerTransportMode = .automobile) {
        let key   = Self.cacheKey(for: day, mode: mode)
        let pairs = Array(zip(day.stops, day.stops.dropFirst()))

        if let cachedSegments = fullyCachedSegments(pairs: pairs, day: day, mode: mode) {
            routes[day.dayIndex] = OptimizerDayRoute(segments: cachedSegments, isLoading: false)
            inFlightKeys[day.dayIndex]  = nil
            inFlightTasks[day.dayIndex]?.cancel()
            inFlightTasks[day.dayIndex] = nil
            return
        }
        if inFlightKeys[day.dayIndex] == key {
            return   // Aynı gün+sıralama+mod zaten hesaplanıyor — tekrar tetikleme.
        }

        // Bu gün için FARKLI bir anahtar hesaplanıyorsa — mod değişmiş
        // olabilir, ya da (pratikte olmaz, itinerary sabit) durak dizilimi
        // — onu iptal et; aynı anahtar değilse bu bir no-op'tur.
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
        // gerektiriyor; "loading" durumunda da geçerli) — bu, mod
        // değiştiğinde ÖNCEKİ modun rotasının ekranda asılı kalmamasını da
        // sağlıyor (bir önceki `routes[day.dayIndex]` burada HEMEN
        // eziliyor). Kısmen önbellekte olan bacaklar bile bu ilk anlık
        // görüntüde henüz yansıtılmaz — asıl (önbellek+ağ karışımı) sonuç
        // aşağıdaki Task'ta üretilir.
        routes[day.dayIndex] = OptimizerDayRoute(
            segments: Self.straightLineSegments(for: day), isLoading: true
        )
        inFlightKeys[day.dayIndex] = key

        let provider = self.provider
        let cache    = self.cache

        let task = Task { [weak self] in
            var segments: [OptimizerRouteSegment] = []
            for (from, to) in pairs {
                if Task.isCancelled { return }

                let legKey = Self.legKey(day: day, from: from, to: to, mode: mode)
                if let cached = cache.coordinates(for: legKey) {
                    // Bu bacak, bu mod için zaten kalıcı önbellekte — ağ
                    // isteği YOK (Req 1/6/7).
                    segments.append(OptimizerRouteSegment(coordinates: cached, isRoaded: true))
                    continue
                }

                let fromCoordinate = CLLocationCoordinate2D(latitude: from.latitude, longitude: from.longitude)
                let toCoordinate   = CLLocationCoordinate2D(latitude: to.latitude, longitude: to.longitude)
                do {
                    let coords = try await provider.route(from: fromCoordinate, to: toCoordinate, mode: mode)
                    // İptal, ağ çağrısı tamamlandıktan SONRA gelmiş olabilir
                    // (bkz. `test_cancelAll_doesNotCrash_andAllowsFreshLoadAfterward`)
                    // — iptal edilmiş bir Task'ın yan etkisi (kalıcı
                    // önbelleğe yazmak dahil) OLMAMALI, bu yüzden yazmadan
                    // ÖNCE tekrar kontrol ediliyor.
                    if Task.isCancelled { return }
                    segments.append(OptimizerRouteSegment(coordinates: coords, isRoaded: true))
                    // Yalnızca BAŞARILI bir bacak kalıcı önbelleğe yazılır
                    // (Req 8/9), bu MODA özgü anahtarla.
                    cache.store(coords, for: legKey)
                } catch {
                    if Task.isCancelled { return }
                    // Bu bacak için rota hesaplanamadı — crash yok, durak
                    // kaybolmuyor, o bacak düz çizgiye düşüyor (Req 3).
                    // Kalıcı önbelleğe HİÇ yazılmıyor — bir sonraki
                    // ziyarette (bu modda) yeniden denenebilir kalır (Req 8).
                    segments.append(OptimizerRouteSegment(
                        coordinates: [fromCoordinate, toCoordinate], isRoaded: false
                    ))
                }
            }
            if Task.isCancelled { return }

            guard let self else { return }
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
