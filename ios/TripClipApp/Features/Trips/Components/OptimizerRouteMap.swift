import SwiftUI
import MapKit

/// `OptimizerMapStop` taşıyan pin — sıra numarası ve gün rengini callout/glyph
/// için saklar. `TripMapView.TripAnnotation` ile aynı desen (mekanın temiz
/// adını ayrıca tutuyoruz, çünkü `title` başında "2. " gibi bir sıra
/// numarası taşıyor ve bunu Apple Haritalar'a öyle geçirmek istemiyoruz).
private final class OptimizerStopAnnotation: MKPointAnnotation {
    var placeName:   String = ""
    var stopID:      String = ""
    var dayIndex:    Int = 0
    var orderIndex:  Int = 0
    var tintColor:   UIColor = .systemTeal
}

/// Bir güne ait rota çizgisi — hangi güne ait olduğunu ve rengini taşıyan
/// `MKPolyline` alt sınıfı (TripMapView'in tek-rota polyline'ının çok-günlü
/// karşılığı). `isRoaded == true` ise bu segment gerçek `MKDirections`
/// sürüş rotası geometrisidir (düz çizilir); `false` ise düz-çizgi
/// fallback'tir (kesikli çizilir) — bkz. `OptimizerRouteCalculator`.
private final class OptimizerDayPolyline: MKPolyline {
    var color:    UIColor = .systemTeal
    var isRoaded: Bool = false
}

/// Optimize edilmiş bir itinerary'nin salt-görüntüleme harita sunumu.
/// `TripMapView`'daki pin/callout/"Apple Haritalar'da aç" desenini paylaşır,
/// ama iki optimizer'a özgü farklılık nedeniyle ayrı bir tip (bkz.
/// docs/ios-trip-optimizer.md "Map view"):
///   - Çok günlü itinerary'lerde her GÜN kendi rengi + kendi rota
///     polyline'ına sahiptir; bir günün son durağıyla ertesi günün ilk
///     durağı arasına ASLA çizgi çekilmez (Req 2 — `OptimizerRouteMapData`
///     zaten günleri ayrı ayrı taşıyor, burada yalnızca her günü kendi
///     overlay'i olarak çiziyoruz).
///   - Koordinatı olmayan duraklar `OptimizerRouteMapData` tarafından zaten
///     elenmiş olarak gelir — burada crash/geocoding riski yok.
///
/// Rota çizgileri MapKit-native DÜZ segmentlerdir — bu milestone hiçbir dış
/// yönlendirme API'si çağırmıyor (Req 6), gerçek yol geometrisini TEMSİL
/// ETMEZ, yalnızca optimizer'ın belirlediği durak sırasını görselleştirir.
struct OptimizerRouteMap: UIViewRepresentable {

    let data:              OptimizerRouteMapData
    /// nil ise tüm günler aynı anda, kendi renkleriyle ayrık gösterilir;
    /// belirli bir gün seçiliyse harita yalnızca o günün duraklarına/
    /// rotasına odaklanır (Req 2 "allow the user to inspect each day's route").
    var selectedDayIndex: Int? = nil
    /// `OptimizerRouteCalculator.routes`'un anlık görüntüsü —
    /// `OptimizerRouteMapSection` tarafından geçirilir. Bu tür MapKit'i
    /// hiç bilmez (`[Int: OptimizerDayRoute]`, düz bir değer tipi); bu
    /// katman yalnızca ÇİZER, hesaplama/iptal/önbellek mantığı burada
    /// yaşamaz (Req 4). Bir gün için henüz hesaplanmış bir rota yoksa
    /// (dictionary'de yoksa) o gün `data`'nın kendi düz-çizgi bütün-gün
    /// polyline'ına düşer — Req 3'ün "fall back to the existing
    /// straight-line visualization" gereksinimi tam da bu varsayılan yol.
    var dayRoutes: [Int: OptimizerDayRoute] = [:]
    /// Şu an odaklanılan/vurgulanan durak — `TripMapView.focusedPin` ile
    /// AYNI desen (bkz. `Coordinator.lastFocusedStopID` karşılaştırması):
    /// yalnızca DEĞİŞTİĞİNDE haritayı o durağa yakınlaştırır ve seçer,
    /// aksi halde kullanıcının kendi kaydırma/yakınlaştırmasını asla ezmez
    /// (Req 7). `data.stop(withID:)` bu kimlikle eşleşen bir durak
    /// bulamazsa (koordinatsız durak — Req 9) hiçbir kamera işlemi
    /// yapılmaz; harita olduğu gibi kalır.
    var selectedStopID: String? = nil
    /// Kullanıcı haritada bir pine DOĞRUDAN dokunduğunda çağrılır (Req 2
    /// "Map → Itinerary"). Yalnızca gerçek kullanıcı dokunuşları için
    /// tetiklenir — `selectedStopID` değiştiği için bu view'ın kendi
    /// programatik `map.selectAnnotation` çağrısı BUNU TETİKLEMEZ (bkz.
    /// `Coordinator.isProgrammaticSelection`), aksi halde SwiftUI state'i
    /// ile MKMapView kamerası arasında sonsuz bir geri-besleme döngüsü
    /// oluşurdu (Req 7 "avoid camera-update loops").
    var onSelectStop: ((OptimizerMapStop) -> Void)? = nil

    /// Gün başına döngüsel renk paleti — teal (mevcut TripMapView rota
    /// rengiyle aynı, 1. gün ya da tek günlü itinerary'ler için tutarlı
    /// kalsın diye) + dört ek ayırt edici ton.
    private static let dayColors: [UIColor] = [
        UIColor(red: 0.247, green: 0.851, blue: 0.769, alpha: 1), // route teal
        UIColor(red: 1.000, green: 0.690, blue: 0.125, alpha: 1), // amber
        UIColor(red: 0.686, green: 0.541, blue: 1.000, alpha: 1), // violet
        UIColor(red: 1.000, green: 0.454, blue: 0.454, alpha: 1), // coral
        UIColor(red: 0.443, green: 0.776, blue: 1.000, alpha: 1), // sky
    ]

    static func color(forDay dayIndex: Int) -> UIColor {
        dayColors[dayIndex % dayColors.count]
    }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.mapType = .standard
        map.showsUserLocation = false
        map.delegate = context.coordinator
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        map.removeAnnotations(map.annotations)
        map.removeOverlays(map.overlays)

        let visibleDays = data.visibleDays(selectedDayIndex: selectedDayIndex)
        guard !visibleDays.isEmpty else { return }

        var allAnnotations: [OptimizerStopAnnotation] = []

        for day in visibleDays {
            let color = Self.color(forDay: day.dayIndex)

            let annotations = day.stops.map { stop -> OptimizerStopAnnotation in
                let a = OptimizerStopAnnotation()
                a.coordinate = CLLocationCoordinate2D(latitude: stop.latitude, longitude: stop.longitude)
                a.title      = "\(stop.orderIndex + 1). \(stop.name)"
                a.subtitle   = data.hasMultipleDays ? "\(day.dayIndex + 1). Gün" : "Haritada aç"
                a.placeName  = stop.name
                a.stopID     = stop.id
                a.dayIndex   = day.dayIndex
                a.orderIndex = stop.orderIndex
                a.tintColor  = color
                return a
            }
            map.addAnnotations(annotations)
            allAnnotations += annotations

            // Aynı güne ait ardışık koordinatlar arasında rota — günler
            // arasında ASLA (Req 2). Gerçek MKDirections sonucu varsa
            // bacak bacak onu, yoksa (henüz hesaplanmadı ya da o bacak
            // için rota bulunamadı) düz-çizgi fallback'i çiziyoruz — hiçbir
            // durumda boş kalmıyor (Req 3).
            if let dayRoute = dayRoutes[day.dayIndex], !dayRoute.segments.isEmpty {
                for segment in dayRoute.segments {
                    let polyline = OptimizerDayPolyline(coordinates: segment.coordinates, count: segment.coordinates.count)
                    polyline.color    = color
                    polyline.isRoaded = segment.isRoaded
                    map.addOverlay(polyline)
                }
            } else if day.stops.count > 1 {
                // Rota hesaplaması henüz hiç tetiklenmemiş (ör. ilk render
                // anı) — v5'ten kalma düz-çizgi bütün-gün polyline'ı.
                let coords = day.stops.map {
                    CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
                }
                let polyline = OptimizerDayPolyline(coordinates: coords, count: coords.count)
                polyline.color = color
                map.addOverlay(polyline)
            }
        }

        // Kamerayı HER güncellemede değiştirmiyoruz; yalnızca gerçek bir
        // durum değişikliği olduğunda — aksi halde kullanıcının kendi
        // pan/zoom'unu ezeriz (Req 7). Coordinator'ın son gördüğü
        // değerlerle KARŞILAŞTIRIP HEMEN GÜNCELLİYORUZ (her render'da doğru
        // kalsınlar diye), sonra hangi kamera işleminin (varsa) yapılacağına
        // karar veriyoruz.
        let coordinator  = context.coordinator
        let dayChanged   = coordinator.lastSelectedDayIndex != selectedDayIndex
        let stopChanged  = selectedStopID != coordinator.lastFocusedStopID
        coordinator.lastSelectedDayIndex = selectedDayIndex
        coordinator.lastFocusedStopID    = selectedStopID
        coordinator.onSelectStop         = onSelectStop

        if stopChanged, let selectedStopID, let match = allAnnotations.first(where: { $0.stopID == selectedStopID }) {
            // Belirli bir durağa odaklan (Req 1/4 "center the map on that
            // stop" / "focus the selected stop") — bu, gün AYNI ZAMANDA
            // değişmiş olsa bile (Req 4 senaryosu) TÜM güne değil yalnızca
            // bu durağa yakınlaşır; "fit the whole day" ile karışmaz.
            coordinator.isProgrammaticSelection = true
            map.setRegion(
                MKCoordinateRegion(
                    center: match.coordinate,
                    span:   MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                ),
                animated: true
            )
            map.selectAnnotation(match, animated: true)
        } else if !coordinator.didFitOnce || dayChanged {
            // İlk görünüş, ya da bir durak odağı OLMADAN gün değişti (ör.
            // gün çipine doğrudan dokunuldu, ya da seçilen durağın
            // koordinatı yoktu — Req 9: geçersiz bir noktaya asla
            // merkezlenmeyen, güvenli bir geri düşüş).
            let coords = visibleDays.flatMap { day in
                day.stops.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
            }
            map.setRegion(boundingRegion(for: coords), animated: coordinator.didFitOnce)
            coordinator.didFitOnce = true
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    /// Tek durak ve iki durak durumlarını da doğru kapsayan sınırlayıcı
    /// bölge (Req 8) — `TripMapView.boundingRegion` ile aynı tarif: min span
    /// tabanı + %40 pay, tek noktada da makul bir zoom seviyesi (min span
    /// sayesinde aşırı yakınlaşmıyor).
    private func boundingRegion(for coords: [CLLocationCoordinate2D]) -> MKCoordinateRegion {
        guard !coords.isEmpty else {
            return MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: 39.0, longitude: 35.0),
                span:   MKCoordinateSpan(latitudeDelta: 10, longitudeDelta: 10)
            )
        }
        let lats = coords.map(\.latitude)
        let lngs = coords.map(\.longitude)
        let center = CLLocationCoordinate2D(
            latitude:  (lats.min()! + lats.max()!) / 2,
            longitude: (lngs.min()! + lngs.max()!) / 2
        )
        let span = MKCoordinateSpan(
            latitudeDelta:  max((lats.max()! - lats.min()!) * 1.4, 0.05),
            longitudeDelta: max((lngs.max()! - lngs.min()!) * 1.4, 0.05)
        )
        return MKCoordinateRegion(center: center, span: span)
    }

    // MARK: - Coordinator (MapKit delegate)

    final class Coordinator: NSObject, MKMapViewDelegate {

        /// Son bölge sığdırması hangi gün seçimi içindi — aynı seçimde
        /// tekrar sığdırmamak (kullanıcının kaydırdığı görünümü korumak)
        /// için, ama seçim gerçekten değiştiğinde yeniden sığdırmak için.
        var lastSelectedDayIndex: Int??
        var didFitOnce = false
        /// Son odaklanılan durak kimliği — `TripMapView.Coordinator.lastFocusedIndex`
        /// ile aynı desen.
        var lastFocusedStopID: String?
        /// `updateUIView`'dan HER render'da yenilenir (struct'lar her
        /// render'da yeniden yaratıldığı için closure'ın kendisi de
        /// değişir) — `didSelect` bunu çağırır.
        var onSelectStop: ((OptimizerMapStop) -> Void)?
        /// `updateUIView`'ın kendi `map.selectAnnotation(...)` çağrısının
        /// tetikleyeceği `didSelect`'i, GERÇEK bir kullanıcı dokunuşundan
        /// ayırt etmek için — aksi halde Itinerary → Map odaklanması
        /// `didSelect`'i tetikler, o da `onSelectStop`'u çağırır, o da
        /// seçimi (aynı değere) tekrar yazar: SwiftUI state'i ile
        /// MKMapView kamerası arasında gereksiz bir geri-besleme turu
        /// (Req 7 "avoid camera-update loops"). Bu bayrak, programatik
        /// seçimden hemen önce `true` yapılır, `didSelect` içinde
        /// TÜKETİLİR (bir sonraki `didSelect` çağrısı tekrar gerçek
        /// sayılır).
        var isProgrammaticSelection = false

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? OptimizerDayPolyline {
                let r = MKPolylineRenderer(polyline: polyline)
                r.strokeColor = polyline.color
                r.lineWidth   = 3
                // Gerçek sürüş rotası düz çizgi; düz-çizgi fallback kesikli —
                // fallback durumu sessizce gizlenmiyor ama engelleyici de
                // değil (Req 3 "make the fallback state explicit ... only
                // if useful").
                r.lineDashPattern = polyline.isRoaded ? nil : [8, 4]
                return r
            }
            return MKOverlayRenderer(overlay: overlay)
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard let stop = annotation as? OptimizerStopAnnotation else { return nil }
            let id = "optimizer-stop"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: id) as? MKMarkerAnnotationView
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: id)
            view.annotation       = annotation
            view.markerTintColor  = stop.tintColor
            view.glyphText        = "\(stop.orderIndex + 1)"
            view.glyphTintColor   = .black
            view.canShowCallout   = true
            let button = UIButton(type: .system)
            button.setImage(UIImage(systemName: "map.fill"), for: .normal)
            button.sizeToFit()
            button.accessibilityLabel = "Apple Haritalar'da aç"
            view.rightCalloutAccessoryView = button
            return view
        }

        /// Bir pine dokunuldu (Req 2 "Map → Itinerary"). `isProgrammaticSelection`
        /// açıksa (Itinerary → Map yönünde BU view'ın kendi `updateUIView`'ı
        /// tetikledi) sessizce tüketilir — yalnızca GERÇEK kullanıcı
        /// dokunuşları `onSelectStop`'a ulaşır.
        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            guard let stop = view.annotation as? OptimizerStopAnnotation else { return }
            if isProgrammaticSelection {
                isProgrammaticSelection = false
                return
            }
            onSelectStop?(OptimizerMapStop(
                id: stop.stopID, dayIndex: stop.dayIndex, orderIndex: stop.orderIndex,
                name: stop.placeName, latitude: stop.coordinate.latitude, longitude: stop.coordinate.longitude
            ))
        }

        /// Baloncuktaki butona basıldı → mekanı Apple Haritalar'da aç. Bu,
        /// Req 5'in yasakladığı OTOMATİK açılış değil — yalnızca kullanıcının
        /// açık bir dokunuşuyla tetiklenir.
        func mapView(_ mapView: MKMapView,
                     annotationView view: MKAnnotationView,
                     calloutAccessoryControlTapped control: UIControl) {
            guard let stop = view.annotation as? OptimizerStopAnnotation else { return }
            let placemark = MKPlacemark(coordinate: stop.coordinate)
            let mapItem   = MKMapItem(placemark: placemark)
            mapItem.name  = stop.placeName
            mapItem.openInMaps()
        }
    }
}
