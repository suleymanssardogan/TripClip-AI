import SwiftUI
import MapKit

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
        let annotations = locations.map { pin -> MKPointAnnotation in
            let a = MKPointAnnotation()
            a.coordinate = CLLocationCoordinate2D(latitude: pin.latitude, longitude: pin.longitude)
            a.title      = "\(pin.index). \(pin.name)"
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
                r.strokeColor = UIColor(red: 0.30, green: 1.00, blue: 0.76, alpha: 0.85)
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
                marker.markerTintColor = UIColor(red: 0.30, green: 1.00, blue: 0.76, alpha: 1)
                marker.glyphTintColor  = .black
                marker.canShowCallout  = true
            }
            return view
        }
    }
}
