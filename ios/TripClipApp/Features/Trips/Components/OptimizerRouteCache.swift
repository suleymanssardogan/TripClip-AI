import Foundation
import CoreLocation

/// `OptimizerRouteCalculator`'ın tek başarılı-bacak rota önbelleği — EKRAN
/// ÖMRÜNÜ AŞAR (bkz. docs/ios-trip-optimizer.md "Persistent Optimizer Route
/// Cache"). `TripClipApp.swift`'te BİR KEZ oluşturulup `.environment()` ile
/// enjekte edilir (`AuthEnvironment` ile AYNI DI deseni) — `OptimizerRouteCalculator`
/// global bir state'i doğrudan bilmez, yalnızca kendisine enjekte edilen bu
/// tek bağımlılığı kullanır (Req 14 "prefer injecting a cache/store
/// dependency rather than making the calculator know about global
/// application state").
///
/// Yalnızca BELLEK İÇİ (Req 2/19): disk/Core Data/SwiftData YOK. Uygulama
/// sonlandığında ya da sistem tarafından arka planda öldürüldüğünde
/// kaybolur — bu KASITLI: her bacak zaten ucuz şekilde yeniden hesaplanabilir
/// (tek bir `MKDirections` isteği), bu yüzden diskte kalıcı tutmanın getirisi
/// (bir sonraki app-launch'ta network isteği tasarrufu) diskin getirdiği
/// karmaşıklığa (şema, geçersiz kılma, migration) değmiyor — bkz. "Neden disk
/// kalıcılığı yok" (docs).
///
/// Saklanan TEK şey: `[CLLocationCoordinate2D]` — düz bir değer tipi.
/// `MKRoute`/`MKMapView`/`MKPolyline`/herhangi bir `Observable`/SwiftUI state
/// asla saklanmaz (Req 11) — haritanın çizmesi için gereken minimum veri
/// budur, `OptimizerRouteMap` zaten bu koordinatlardan kendi
/// `MKPolyline`'ını her çizimde yeniden üretiyor.
// @Observable: mekanik bir gereklilik — `AuthEnvironment` ile AYNI
// `.environment(_:)`/`@Environment(Type.self)` enjeksiyon mekanizması
// (Observation framework) buna ihtiyaç duyuyor. Reaktivite için DEĞİL: hiçbir
// SwiftUI View bu tipin özelliklerini doğrudan okumuyor/gözlemlemiyor
// (yalnızca `OptimizerRouteCalculator` içeriden erişiyor; UI'a reaktif
// yüzey `OptimizerRouteCalculator.routes` üzerinden, o zaten kendi
// `@Observable`'ı ile sağlanıyor).
@MainActor
@Observable
final class OptimizerRouteCache {

    /// Req 11 "do not create an unbounded cache": basit bir LRU sınırı.
    /// Tek bir oturumda gezilen itinerary/gün/bacak sayısı makul biçimde
    /// küçük kalır (kullanıcı en fazla birkaç itinerary'i, birkaç kez,
    /// birer birkaç günlük olarak gezer) — 500 bacak (tipik 3-5 durak/gün ×
    /// onlarca itinerary) cömert ama sınırsız olmayan bir üst sınır.
    private let capacity: Int
    private var storage: [String: [CLLocationCoordinate2D]] = [:]
    /// En eskiden en yeniye erişim sırası — `evictLeastRecentlyUsedIfNeeded`
    /// bunun başından siler. Küçük (≤ `capacity`) olduğundan doğrusal
    /// arama/kaldırma burada gereksiz bir karmaşıklık DEĞİL (Req 12 "do not
    /// over-engineer this" — uygun bir çift-bağlı-liste tabanlı LRU'ya
    /// gerek yok).
    private var accessOrder: [String] = []

    init(capacity: Int = 500) {
        self.capacity = capacity
    }

    /// `legKey` için daha önce başarıyla önbelleğe alınmış bir rota var mı —
    /// varsa döner ve LRU sırasında "en yeni" konuma taşır, yoksa `nil`
    /// (arayan taraf `MKDirections`'a normal şekilde başvurur).
    func coordinates(for legKey: String) -> [CLLocationCoordinate2D]? {
        guard let hit = storage[legKey] else { return nil }
        touch(legKey)
        return hit
    }

    /// Yalnızca BAŞARILI bir bacak sonucu buraya yazılmalı — arayan taraf
    /// (`OptimizerRouteCalculator.load`) başarısız/düz-çizgi fallback
    /// bacakları asla `store` ile çağırmaz (Req 8/9: başarısız bir bacak
    /// kalıcı önbelleğe hiç girmez, bir sonraki ziyarette yeniden denenebilir
    /// kalır).
    func store(_ coordinates: [CLLocationCoordinate2D], for legKey: String) {
        if storage[legKey] == nil {
            accessOrder.append(legKey)
        } else {
            touch(legKey)
        }
        storage[legKey] = coordinates
        evictLeastRecentlyUsedIfNeeded()
    }

    private func touch(_ legKey: String) {
        if let index = accessOrder.firstIndex(of: legKey) {
            accessOrder.remove(at: index)
        }
        accessOrder.append(legKey)
    }

    private func evictLeastRecentlyUsedIfNeeded() {
        while storage.count > capacity, !accessOrder.isEmpty {
            let oldest = accessOrder.removeFirst()
            storage.removeValue(forKey: oldest)
        }
    }
}
