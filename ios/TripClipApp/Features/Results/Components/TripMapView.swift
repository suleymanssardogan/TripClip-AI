import SwiftUI
import MapKit

/// Mekanın temiz adını taşır. `MKPointAnnotation.title` "2. Kaleiçi" gibi
/// sıra numarasıyla gösterildiği için Apple Maps'e o adı geçirmek istemiyoruz.
final class TripAnnotation: MKPointAnnotation {
    var placeName: String = ""
}

struct TripMapView: UIViewRepresentable {

    let locations: [LocationPin]
    let route:     [RoutePoint]?

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
        let annotations = locations.map { pin -> TripAnnotation in
            let a = TripAnnotation()
            a.coordinate = CLLocationCoordinate2D(latitude: pin.latitude, longitude: pin.longitude)
            a.title      = "\(pin.index). \(pin.name)"
            a.subtitle   = "Haritada aç"
            a.placeName  = pin.name
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

        // ── Fit region ───────────────────────────────────────────────────────
        let coords = locations.map {
            CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
        }
        let region = boundingRegion(for: coords)
        map.setRegion(region, animated: false)
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
