import SwiftUI
import MapKit

/// Mekanın temiz adını taşır. `MKPointAnnotation.title` "2. Kaleiçi" gibi
/// sıra numarasıyla gösterildiği için Apple Maps'e o adı geçirmek istemiyoruz.
final class TripAnnotation: MKPointAnnotation {
    var placeName: String = ""
    /// LocationPin.index — listeden gelen odak isteğini eşleştirmek için.
    var pinIndex: Int = 0
}

struct TripMapView: UIViewRepresentable {

    let locations: [LocationPin]
    let route:     [RoutePoint]?
    /// Listeden bir mekana basıldığında buraya gelir; harita o pine zoom yapıp
    /// baloncuğunu açar. nil ise tüm rotayı kapsayan varsayılan görünüm.
    var focusedPin: LocationPin? = nil
    /// Kullanıcı haritada bir pine GERÇEKTEN dokunduğunda çağrılır (Req "Map
    /// → Itinerary" — bkz. `OptimizerRouteMap.swift`'in AYNI
    /// `didSelect`/`isProgrammaticSelection` deseni). Opsiyonel ve varsayılan
    /// `nil`: bu view'ın diğer çağıranı (`ResultsView`) bu yönü hiç
    /// kullanmıyor, geriye dönük UYUMLU.
    var onSelectPin: ((LocationPin) -> Void)? = nil

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.mapType      = .standard
        map.showsUserLocation = false
        map.delegate     = context.coordinator
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        map.removeAnnotations(map.annotations)
        map.removeOverlays(map.overlays)

        guard !locations.isEmpty else { return }

        // ── Pins ────────────────────────────────────────────────────────────
        // Baloncuktaki numara listedeki POZİSYON; pin.index ise sunucudaki kalıcı
        // kimlik (durak silinince boşluk bırakır). İkisini karıştırmamak için
        // gösterim offset'ten, eşleme index'ten geliyor.
        let annotations = locations.enumerated().map { offset, pin -> TripAnnotation in
            let a = TripAnnotation()
            a.coordinate = CLLocationCoordinate2D(latitude: pin.latitude, longitude: pin.longitude)
            a.title      = "\(offset + 1). \(pin.name)"
            a.subtitle   = "Haritada aç"
            a.placeName  = pin.name
            a.pinIndex   = pin.index
            return a
        }
        map.addAnnotations(annotations)

        // ── Route polyline ───────────────────────────────────────────────────
        if let route, route.count > 1 {
            let coords = route.map {
                CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
            }
            let polyline = MKPolyline(coordinates: coords, count: coords.count)
            map.addOverlay(polyline)
        }

        // ── Görünüm ──────────────────────────────────────────────────────────
        // Bölgeyi HER güncellemede değiştirmiyoruz; aksi halde alakasız bir
        // state değişimi kullanıcının kaydırdığı haritayı başa sarıyordu.
        let coordinator = context.coordinator
        coordinator.onSelectPin = onSelectPin

        if let focusedPin, focusedPin.index != coordinator.lastFocusedIndex {
            // Listeden yeni bir mekana basıldı → o mekana zoom yap ve seç.
            coordinator.lastFocusedIndex = focusedPin.index
            let center = CLLocationCoordinate2D(latitude: focusedPin.latitude,
                                                longitude: focusedPin.longitude)
            map.setRegion(
                MKCoordinateRegion(
                    center: center,
                    span:   MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02)
                ),
                animated: true
            )
            if let match = annotations.first(where: { $0.pinIndex == focusedPin.index }) {
                // Bu, `didSelect`'i PROGRAMATİK olarak tetikleyecek — gerçek bir
                // kullanıcı dokunuşundan ayırt etmek gerekiyor, aksi halde
                // Itinerary → Map odaklanması `onSelectPin`'i tekrar çağırır ve
                // SwiftUI state'iyle MKMapView arasında gereksiz bir geri-besleme
                // turu oluşur (bkz. OptimizerRouteMap.swift'in AYNI deseni).
                coordinator.isProgrammaticSelection = true
                map.selectAnnotation(match, animated: true)
            }
        } else if !coordinator.didSetInitialRegion {
            let coords = locations.map {
                CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
            }
            map.setRegion(boundingRegion(for: coords), animated: false)
            coordinator.didSetInitialRegion = true
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

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

        /// Son odaklanılan pin — aynı odak için tekrar zoom yapmamak, ve
        /// odak değişmediğinde kullanıcının kaydırdığı görünümü korumak için.
        var lastFocusedIndex:    Int?
        var didSetInitialRegion = false
        /// `updateUIView`'dan HER render'da yenilenir — bkz. `onSelectPin`'in
        /// kendi doc yorumu.
        var onSelectPin: ((LocationPin) -> Void)?
        /// `updateUIView`'ın kendi `map.selectAnnotation(...)` çağrısının
        /// tetikleyeceği `didSelect`'i GERÇEK bir kullanıcı dokunuşundan ayırt
        /// etmek için — bkz. `OptimizerRouteMap.swift`'in AYNI bayrağı.
        var isProgrammaticSelection = false

        func mapView(_ mapView: MKMapView,
                     rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? MKPolyline {
                let r = MKPolylineRenderer(polyline: polyline)
                r.strokeColor = UIColor(red: 0.247, green: 0.851, blue: 0.769, alpha: 0.85) // Route teal
                r.lineWidth   = 3
                r.lineDashPattern = [8, 4]
                return r
            }
            return MKOverlayRenderer(overlay: overlay)
        }

        func mapView(_ mapView: MKMapView,
                     viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard !(annotation is MKUserLocation) else { return nil }
            let id  = "pin"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: id)
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: id)
            if let marker = view as? MKMarkerAnnotationView {
                marker.markerTintColor = UIColor(red: 0.247, green: 0.851, blue: 0.769, alpha: 1) // Route teal
                marker.glyphTintColor  = .black
                marker.canShowCallout  = true
                // Baloncuktaki yol tarifi butonu — basınca Apple Maps açılır.
                let button = UIButton(type: .system)
                button.setImage(UIImage(systemName: "map.fill"), for: .normal)
                button.sizeToFit()
                button.accessibilityLabel = "Apple Haritalar'da aç"
                marker.rightCalloutAccessoryView = button
            }
            return view
        }

        /// Kullanıcı bir pine dokundu (Req "Map → Itinerary"). Programatik
        /// seçim (Itinerary → Map yönünde `updateUIView`'ın kendi
        /// `map.selectAnnotation` çağrısı) burayı SESSİZCE tüketir — yalnızca
        /// gerçek kullanıcı dokunuşları `onSelectPin`'e ulaşır (bkz.
        /// `isProgrammaticSelection`'ın kendi doc yorumu).
        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            guard let annotation = view.annotation as? TripAnnotation else { return }
            if isProgrammaticSelection {
                isProgrammaticSelection = false
                return
            }
            onSelectPin?(LocationPin(
                index: annotation.pinIndex, name: annotation.placeName, type: "location",
                latitude: annotation.coordinate.latitude, longitude: annotation.coordinate.longitude,
                importance: 1.0
            ))
        }

        /// Baloncuktaki butona basıldı → mekanı Apple Haritalar'da aç.
        func mapView(_ mapView: MKMapView,
                     annotationView view: MKAnnotationView,
                     calloutAccessoryControlTapped control: UIControl) {
            guard let annotation = view.annotation else { return }

            let placemark = MKPlacemark(coordinate: annotation.coordinate)
            let mapItem   = MKMapItem(placemark: placemark)
            // Sıra numarasız temiz ad — Apple Maps'te "2. Kaleiçi" görünmesin.
            mapItem.name = (annotation as? TripAnnotation)?.placeName
                ?? annotation.title.flatMap { $0 }

            // Yol tarifi modu YOK: Apple Maps mekanı doğrudan göstersin.
            // Directions modu, konum izni verilmemişse veya mevcut konum
            // alınamıyorsa (ör. Simulator) rotalayamayıp haritayı alakasız bir
            // bölgede açıyor. Mekanı göstermek her durumda çalışır, kullanıcı
            // yol tarifini Maps içinden tek dokunuşla alabilir.
            mapItem.openInMaps()
        }
    }
}
