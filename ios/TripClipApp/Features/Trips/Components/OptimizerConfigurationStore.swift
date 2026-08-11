import Foundation

/// `OptimizerConfiguration`'ın (yer seçimi, süre, saat, tarih, taşıma modu)
/// EKRAN ÖMRÜNÜ AŞAN, UYGULAMA OTURUMU boyunca yaşayan önbelleği — bkz.
/// docs/ios-trip-optimizer.md "Persistent Optimizer Configuration".
/// `OptimizerRouteCache`/`OptimizerSelectionStore` ile AYNI DI deseni:
/// `TripClipApp.swift`'te BİR KEZ oluşturulup `.environment()` ile enjekte
/// edilir, bir global singleton (`static let shared`) İCAT EDİLMİYOR.
///
/// Yalnızca BELLEK İÇİ: disk/`UserDefaults`/Keychain/Core Data/SwiftData
/// YOK — uygulama oturumu bittiğinde kaybolur, bu KASITLI (Req 3).
///
/// Anahtar `Trip.id` (`tripID: Int`) — trip A'nın yapılandırması trip B
/// açılırken ASLA görünmez, çünkü ikisi ayrı dictionary anahtarları
/// altında yaşar (Req 12, CRİTİK).
///
/// `OptimizerSelectionStore`'dan (hangi gün/durak ODAKLANMIŞ) VE
/// `OptimizerRouteCache`'ten (hesaplanmış rota GEOMETRİSİ) kasıtlı olarak
/// AYRI — bu üçü farklı kavramlar, birleştirilmedi (Req 13).
// @Observable: mekanik bir gereklilik — AYNI `.environment(_:)`/
// `@Environment(Type.self)` enjeksiyon mekanizması (bkz. `OptimizerRouteCache`/
// `OptimizerSelectionStore`'un kendi doc yorumları) — reaktivite için DEĞİL,
// hiçbir SwiftUI View bu tipin state'ini doğrudan okumuyor/gözlemlemiyor
// (`TripOptimizerConfigViewModel` yalnızca `configuration(for:)`/`save(_:for:)`'u
// çağırıp sonucu kendi state'ine kopyalar).
@MainActor
@Observable
final class OptimizerConfigurationStore {

    private var configurations: [Int: OptimizerConfiguration] = [:]

    func configuration(for tripID: Int) -> OptimizerConfiguration? {
        configurations[tripID]
    }

    func save(_ configuration: OptimizerConfiguration, for tripID: Int) {
        configurations[tripID] = configuration
    }

    func remove(for tripID: Int) {
        configurations.removeValue(forKey: tripID)
    }

    /// Yalnızca `transportMode`'u günceller — bkz. docs/ios-trip-optimizer.md
    /// "Persistent Optimizer Transport Mode Sync". `OptimizerRouteMapSection`
    /// (harita) `OptimizerConfigurationStore`'un varlığını BİLMEZ (mimari
    /// kısıt) — bu yüzden `TripOptimizerView`, haritanın raporladığı mod
    /// değişikliğini tek bir çağrıyla BURAYA iletir, birleştirme/varsayılan
    /// MANTIĞI TripOptimizerView'da DEĞİL, burada, tek bir yerde yaşar
    /// (`persistConfiguration()`'ın kendi "merkezi kalıcılık" ilkesiyle
    /// AYNI desen).
    ///
    /// Bu trip için ZATEN bir yapılandırma varsa (yapılandırma ekranı en az
    /// bir kez ziyaret edilmiş/`.generate` akışı buradan geçmiş) yalnızca
    /// `transportMode` alanı değişir — `selectedPlaceIDs`/`durationDays`/
    /// saat/tarih AYNEN KORUNUR (Req "mode change must not affect places/
    /// duration/time/date").
    ///
    /// Yoksa (`.viewSaved` akışı bu trip için yapılandırma ekranından HİÇ
    /// geçmemiş — Itinerary History'den doğrudan açılmış olabilir) `nil`
    /// selectedPlaceIDs YERİNE çağıranın sağladığı `fallbackSelectedPlaceIDs`
    /// ile yeni bir kayıt oluşturulur (`OptimizerConfiguration.defaults`
    /// aracılığıyla). BOŞ bir küme kullanmak YANLIŞ olurdu: bu trip için
    /// DAHA SONRA yapılandırma ekranı açılırsa `reconciled(saved:...)`
    /// kaydedilmiş `selectedPlaceIDs`'i geçerli duraklarla KESİŞTİRİR — boş
    /// bir küme kesişimi her zaman boştur, yani kullanıcı hiçbir mekan
    /// seçilmemiş olarak karşılanırdı (sessiz, şaşırtıcı bir regresyon).
    /// Çağıran (`TripOptimizerView`) bu fallback için o an GÖRÜNTÜLENEN
    /// itinerary'nin kendi duraklarını geçirir — en azından "kullanıcının
    /// az önce baktığı mekanlar" kadar makul bir başlangıç noktası.
    func updateTransportMode(_ mode: OptimizerTransportMode, for tripID: Int, fallbackSelectedPlaceIDs: Set<Int>) {
        if var existing = configurations[tripID] {
            existing.transportMode = mode
            configurations[tripID] = existing
        } else {
            var config = OptimizerConfiguration.defaults(selectedPlaceIDs: fallbackSelectedPlaceIDs)
            config.transportMode = mode
            configurations[tripID] = config
        }
    }
}
