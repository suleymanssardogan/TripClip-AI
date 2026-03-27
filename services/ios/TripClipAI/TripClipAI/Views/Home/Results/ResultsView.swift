import SwiftUI
import MapKit

struct ResultsView: View {
    let videoId: Int
    @State private var videoData: VideoResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var loadingDots = ""
    
    let noiseWords = ["YİYECEK VE i", "Denemeniz Gerekenler", "LÜTFEN", "MASAYA", "İÇECEK", "ECEK"]
    
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            if isLoading {
                VStack(spacing: 24) {
                    ZStack {
                        Circle()
                            .fill(Color.blue.opacity(0.15))
                            .frame(width: 100, height: 100)
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(1.5)
                    }
                    Text("AI analiz ediyor\(loadingDots)")
                        .font(.headline)
                        .foregroundColor(.white)
                    Text("Video işleniyor, lütfen bekleyin...")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.5))
                }
            } else if let video = videoData {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        
                        // Harita
                        if let locations = video.aiResults?.nominatim?.deduplicatedLocations,
                           !locations.isEmpty {
                            DarkCard(title: "🗺️ Harita") {
                                MapView(locations: locations)
                                    .frame(height: 200)
                                    .cornerRadius(12)
                            }
                        }
                        
                        // Şehirler
                        if let locations = video.aiResults?.nominatim?.deduplicatedLocations,
                           !locations.isEmpty {
                            DarkCard(title: "🏙️ Şehirler") {
                                VStack(alignment: .leading, spacing: 10) {
                                    ForEach(locations, id: \.originalName) { location in
                                        HStack(spacing: 12) {
                                            Image(systemName: "mappin.circle.fill")
                                                .foregroundColor(.blue)
                                                .font(.title3)
                                            Text(location.originalName)
                                                .foregroundColor(.white)
                                                .font(.subheadline)
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Mekanlar (OCR POIs)
                        if let pois = video.aiResults?.ocrPois {
                            let filteredPois = pois.filter { !noiseWords.contains($0) }
                            if !filteredPois.isEmpty {
                                DarkCard(title: "📍 Mekanlar") {
                                    VStack(alignment: .leading, spacing: 10) {
                                        ForEach(filteredPois, id: \.self) { poi in
                                            HStack(spacing: 12) {
                                                Image(systemName: "fork.knife.circle.fill")
                                                    .foregroundColor(.orange)
                                                    .font(.title3)
                                                Text(poi)
                                                    .foregroundColor(.white)
                                                    .font(.subheadline)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Travel Tips
                        if let tips = video.aiResults?.rag?.travelTips?.tips,
                           !tips.isEmpty {
                            DarkCard(title: "💡 Seyahat İpuçları") {
                                VStack(alignment: .leading, spacing: 16) {
                                    ForEach(tips, id: \.location) { tip in
                                        VStack(alignment: .leading, spacing: 8) {
                                            HStack {
                                                Image(systemName: "location.fill")
                                                    .foregroundColor(.orange)
                                                Text(tip.location)
                                                    .font(.headline)
                                                    .foregroundColor(.white)
                                            }
                                            Text(tip.tip)
                                                .font(.caption)
                                                .foregroundColor(.white.opacity(0.7))
                                                .lineLimit(4)
                                        }
                                        .padding(12)
                                        .background(Color.white.opacity(0.05))
                                        .cornerRadius(10)
                                    }
                                }
                            }
                        }
                        
                        // Özet
                        if let summary = video.aiResults?.rag?.travelTips?.summary {
                            DarkCard(title: "📝 Gezi Özeti") {
                                Text(summary)
                                    .font(.subheadline)
                                    .foregroundColor(.white.opacity(0.8))
                                    .lineSpacing(4)
                            }
                        }
                        
                        // Stats
                        if let processing = video.aiResults?.processingTime {
                            DarkCard(title: "⚡ İşlem Bilgisi") {
                                HStack(spacing: 20) {
                                    StatItem(value: "\(Int(processing))s", label: "Süre")
                                    StatItem(value: "\(video.duration ?? 0)s", label: "Video")
                                    StatItem(value: "\(video.aiResults?.detections?.count ?? 0)", label: "Nesne")
                                }
                            }
                        }
                    }
                    .padding()
                }
            } else if let error = errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 50))
                        .foregroundColor(.orange)
                    Text(error)
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }
        }
        .navigationTitle("Gezi Planın")
        .navigationBarTitleDisplayMode(.large)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            startLoadingAnimation()
            await pollVideoStatus()
        }
    }
    
    func startLoadingAnimation() {
        Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { timer in
            if !isLoading { timer.invalidate(); return }
            loadingDots = loadingDots.count >= 3 ? "" : loadingDots + "."
        }
    }
    
    func pollVideoStatus() async {
        for _ in 0..<120 {
            do {
                let video = try await APIService.shared.getVideoStatus(id: videoId)
                if video.status == "completed" {
                    await MainActor.run {
                        videoData = video
                        isLoading = false
                    }
                    return
                } else if video.status == "failed" {
                    await MainActor.run {
                        errorMessage = "Video işleme başarısız"
                        isLoading = false
                    }
                    return
                }
                try await Task.sleep(nanoseconds: 5_000_000_000)
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
                return
            }
        }
        await MainActor.run {
            errorMessage = "Zaman aşımı"
            isLoading = false
        }
    }
}

struct MapView: UIViewRepresentable {
    let locations: [EnrichedLocation]
    
    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.mapType = .standard
        return mapView
    }
    
    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.removeAnnotations(mapView.annotations)
        
        var coordinates: [CLLocationCoordinate2D] = []
        
        for location in locations {
            guard let lat = location.placeData?.location?.lat,
                  let lng = location.placeData?.location?.lng else { continue }
            
            let coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)
            coordinates.append(coordinate)
            
            let annotation = MKPointAnnotation()
            annotation.coordinate = coordinate
            annotation.title = location.originalName
            mapView.addAnnotation(annotation)
        }
        
        if let first = coordinates.first {
            let region = MKCoordinateRegion(
                center: first,
                latitudinalMeters: 10000,
                longitudinalMeters: 10000
            )
            mapView.setRegion(region, animated: false)
        }
    }
}

struct DarkCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
                .foregroundColor(.white)
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.07))
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.white.opacity(0.1), lineWidth: 1)
        )
    }
}

struct StatItem: View {
    let value: String
    let label: String
    
    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(.white)
            Text(label)
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    NavigationStack {
        ResultsView(videoId: 1)
    }
}
