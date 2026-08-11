import MapKit

/// Optimizer rota haritasının GÖSTERİM tercihi — rota GEOMETRİSİNİN hangi
/// ulaşım moduyla (`MKDirections`) hesaplanacağı. Yalnızca haritanın çizdiği
/// rota çizgisini etkiler; backend'in optimizer'ın belirlediği durak SIRASI
/// bundan tamamen bağımsız ve hiç değişmez — bkz.
/// docs/ios-trip-optimizer.md "Optimizer Route Transport Mode".
///
/// `MKDirectionsTransportType` SwiftUI state'ine ya da önbellek modellerine
/// (`OptimizerRouteCache`, `OptimizerDayRoute`) SIZMAZ — bu tip onun yerine
/// geçiyor; ham MapKit tipi yalnızca `mapKitType` üzerinden, routing
/// katmanının (`MKDirectionsRoutingProvider`) kendi içinde okunuyor.
///
/// `.automobile`/`.walking`/`.transit` — bkz. docs/ios-trip-optimizer.md
/// "Transit Transport Mode". Transit, `MKDirections`'ın kendisi kadar
/// güvenilir: bölgeye/saate/Apple Haritalar'ın toplu taşıma kapsama
/// verisine bağlı olarak rota bulunamayabilir — bu durum bir hata DEĞİL,
/// zaten var olan (Req 3, v6'dan beri) düz-çizgi fallback mekanizmasıyla
/// tamamen ele alınır; bu tip kendisi hiçbir kullanılabilirlik/zamanlama
/// varsayımı YAPMAZ, yalnızca `MKDirectionsTransportType`'a giden ham
/// eşlemeyi taşır.
enum OptimizerTransportMode: String, CaseIterable, Hashable, Sendable {
    case automobile
    case walking
    case transit

    /// Seçici çipinde gösterilen kısa Türkçe etiket. Tüm görüntüleme
    /// metadatası (başlık/simge/erişilebilirlik) BURADA merkezi kalır —
    /// `OptimizerRouteMapSection`/`TripOptimizerConfigView`'ın hiçbiri
    /// kendi ham string/simge eşlemesini İCAT ETMEZ, ikisi de bu
    /// property'leri okur (Req 2 "do not hardcode transport-mode labels
    /// throughout the UI").
    var title: String {
        switch self {
        case .automobile: return "Araba"
        case .walking:    return "Yürüyüş"
        case .transit:    return "Toplu Taşıma"
        }
    }

    /// VoiceOver etiketi — `title`'dan daha açıklayıcı, day chip'lerin
    /// `chipAccessibilityLabel` deseniyle AYNI yaklaşım (bkz.
    /// `OptimizerMapDay.chipAccessibilityLabel`).
    var accessibilityLabel: String {
        switch self {
        case .automobile: return "Araba ile rota"
        case .walking:    return "Yürüyüş rotası"
        case .transit:    return "Toplu taşıma rotası"
        }
    }

    /// Seçici çipindeki SF Symbol — native, sistem tarafından zaten
    /// yerelleştirilmiş/erişilebilir bir simge seti (Req 2 "use native
    /// SwiftUI controls"). `tram.fill` Apple Haritalar'ın kendi toplu
    /// taşıma glifiyle tutarlı.
    var symbolName: String {
        switch self {
        case .automobile: return "car.fill"
        case .walking:    return "figure.walk"
        case .transit:    return "tram.fill"
        }
    }

    /// Bu tipin TEK MapKit sızıntı noktası — `MKDirectionsRoutingProvider`
    /// dışında hiçbir yerde okunmamalı (Req 3: `MKDirectionsTransportType`
    /// SwiftUI/ViewModel/Cache/Calculator/Configuration/domain katmanlarına
    /// SIZMAZ).
    var mapKitType: MKDirectionsTransportType {
        switch self {
        case .automobile: return .automobile
        case .walking:    return .walking
        case .transit:    return .transit
        }
    }
}
