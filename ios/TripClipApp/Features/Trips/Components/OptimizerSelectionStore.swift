import Foundation

/// `OptimizerSelection`'ın (gün + durak seçimi) EKRAN ÖMRÜNÜ AŞAN, UYGULAMA
/// OTURUMU boyunca yaşayan önbelleği — bkz. docs/ios-trip-optimizer.md
/// "Persistent Optimizer Map Selection". `OptimizerRouteCache` ile AYNI DI
/// deseni: `TripClipApp.swift`'te BİR KEZ oluşturulup `.environment()` ile
/// enjekte edilir, bir global singleton (`static let shared`) İCAT
/// EDİLMİYOR (Req 11).
///
/// Yalnızca BELLEK İÇİ (Req 1): disk/`UserDefaults`/Keychain/Core
/// Data/SwiftData YOK — bir seçim son derece ucuz UI state'i (iki opsiyonel
/// değer), kalıcı depolamayı hak etmiyor. Uygulama sonlandığında/oturum
/// bittiğinde kaybolur; bu KASITLI.
///
/// Anahtar `Itinerary.id` (Req 3, CRİTİK: "itinerary-scoped") — itinerary
/// A'nın seçimi itinerary B açılırken ASLA görünmez, çünkü ikisi ayrı
/// dictionary anahtarları altında, birbirinden habersiz yaşar.
// @Observable: mekanik bir gereklilik — AYNI `.environment(_:)`/
// `@Environment(Type.self)` enjeksiyon mekanizması (bkz. `OptimizerRouteCache`'in
// kendi doc yorumu) — reaktivite için DEĞİL, hiçbir SwiftUI View bu tipin
// state'ini doğrudan okumuyor/gözlemlemiyor (`TripOptimizerView` yalnızca
// `resolveSelection(for:)`'u çağırıp sonucu kendi `@State`'ine atıyor).
@MainActor
@Observable
final class OptimizerSelectionStore {

    private var selections: [Int: OptimizerSelection] = [:]

    /// Ham okuma — DOĞRULAMA YAPMAZ, yalnızca son bilinen (kaydedilmiş)
    /// seçimi olduğu gibi döner. Testlerin depolama/izolasyon davranışını
    /// `resolveSelection(for:)`'un doğrulama mantığından AYRI test
    /// edebilmesi için var; üretim kodu genelde `resolveSelection(for:)`
    /// kullanır.
    func rawSelection(for itineraryID: Int) -> OptimizerSelection? {
        selections[itineraryID]
    }

    /// O ANKİ, zaten geçerli olan (çünkü canlı bir ekranın gerçek
    /// seçiminden geliyor) seçimi saklar. Doğrulama YOK — doğrulama yalnızca
    /// `resolveSelection(for:)`'da, GERİ OKURKEN yapılır, çünkü staleness
    /// yalnızca iki ziyaret ARASINDA (itinerary yeniden üretildi, bir durak
    /// silindi, vb.) oluşabilir, tek bir canlı oturum içinde değil.
    func store(_ selection: OptimizerSelection, for itineraryID: Int) {
        selections[itineraryID] = selection
    }

    /// Verilen itinerary için GÖSTERİLMEYE HAZIR, DOĞRULANMIŞ bir seçim
    /// döner (Req 5, CRİTİK: "never blindly restore the stored selection").
    /// Kayıtlı bir seçim yoksa mevcut varsayılan davranışı AYNEN korur
    /// (`OptimizerSelection()` — `dayIndex: nil` = "Tümü", bu milestone
    /// öncesindeki davranışla BİREBİR aynı).
    ///
    /// Doğrulama sırası (bkz. docs "Fallback behavior" — her adım bir
    /// önceki başarısız olursa devreye girer):
    ///   1. Kayıtlı bir `stopID` varsa, o durağı İTİNERARY'NİN HER
    ///      GÜNÜNDE ara (yalnızca kayıtlı günde değil) — bulunursa,
    ///      durağın KENDİ GÜNCEL gününe bağlı olarak geri yükle (Req 6
    ///      "moved to another day: follow the stop, not the old day").
    ///      Bu TEK arama, "hiçbir şey taşınmadı" (yaygın durum) ile
    ///      "durak başka güne taşındı" durumlarını AYNI kod yoluyla,
    ///      doğal biçimde kapsıyor.
    ///   2. Durak bulunamadıysa (silinmiş) VEYA hiç durak kaydedilmemişse,
    ///      kayıtlı `dayIndex`'i doğrula: hâlâ geçerliyse (o gün itinerary'de
    ///      hâlâ varsa) günü koru, durağı temizle (Req 6 "keep the stored
    ///      day if that day is still valid").
    ///   3. Kayıtlı gün de artık geçersizse (itinerary küçüldü/yeniden
    ///      üretildi), ilk mevcut güne düş (Req 6 "fallback to first
    ///      available day, no selected stop") — `itinerary.days.first`
    ///      boşsa (boş itinerary) bu doğal olarak `nil`'e düşer, ayrı bir
    ///      "boş itinerary" özel durumuna GEREK YOK (Req 6'nın kendi
    ///      "empty itinerary → nil/nil" kuralı bu genel yoldan zaten
    ///      sağlanıyor).
    ///   4. Kayıtlı gün de hiç yoksa (`nil` — "Tümü" kaydedilmişti),
    ///      "Tümü" olarak kalır.
    ///
    /// O(toplam durak+gün sayısı) — network isteği, veritabanı sorgusu ya
    /// da rota hesaplaması YOK (Req 16).
    func resolveSelection(for itinerary: Itinerary) -> OptimizerSelection {
        guard let stored = selections[itinerary.id] else {
            return OptimizerSelection()
        }

        if let stopID = stored.stopID {
            for day in itinerary.days {
                if let stop = day.stops.first(where: { $0.id == stopID }) {
                    return .focusing(dayIndex: day.dayIndex, stopID: stop.id)
                }
            }
        }

        if let storedDayIndex = stored.dayIndex {
            if itinerary.days.contains(where: { $0.dayIndex == storedDayIndex }) {
                return OptimizerSelection(dayIndex: storedDayIndex, stopID: nil)
            }
            return OptimizerSelection(dayIndex: itinerary.days.first?.dayIndex, stopID: nil)
        }

        return OptimizerSelection(dayIndex: nil, stopID: nil)
    }
}
