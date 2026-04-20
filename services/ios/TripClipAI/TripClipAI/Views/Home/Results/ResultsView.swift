import SwiftUI
import MapKit

struct ResultsView: View {
    let videoId: Int
    var preloadedData: AIResults? = nil
    @State private var videoData: VideoResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var loadingDots = ""
    @State private var showShareSheet = false
    @State private var pdfData: Data?

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if isLoading {
                loadingView
            } else if let video = videoData {
                resultsContent(video: video)
            } else if let error = errorMessage {
                errorView(message: error)
            }
        }
        .navigationTitle("Gezi Planın")
        .navigationBarTitleDisplayMode(.large)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            if let video = videoData {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        pdfData = PDFExportService.generateTripPDF(video: video)
                        showShareSheet = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundColor(.white)
                    }
                }
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let data = pdfData {
                ShareSheet(items: [data])
            }
        }
        .task {
            if let preloaded = preloadedData {
                videoData = VideoResponse(id: videoId, filename: "", status: "completed", duration: nil, aiResults: preloaded)
                isLoading = false
            } else {
                startLoadingAnimation()
                await pollVideoStatus()
            }
        }
    }

    // MARK: - Loading

    var loadingView: some View {
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
    }

    // MARK: - Error

    func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 50))
                .foregroundColor(.orange)
            Text(message)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
        }
        .padding()
    }

    // MARK: - Results

    @ViewBuilder
    func resultsContent(video: VideoResponse) -> some View {
        let ai = video.aiResults
        let locations = ai?.nominatim?.deduplicatedLocations ?? []
        let ocrTexts = ai?.ocr?.extractedTexts ?? []
        let nerLocations = ai?.ner?.extractedLocations ?? []
        let ocrPois = ai?.ocrPois ?? []
        let tips = ai?.rag?.travelTips?.tips ?? []
        let summary = ai?.rag?.travelTips?.summary
        let transcript = ai?.audio?.transcription?.transcript

        let hasAnyData = !locations.isEmpty || !ocrTexts.isEmpty ||
                         !nerLocations.isEmpty || !ocrPois.isEmpty ||
                         !tips.isEmpty || transcript != nil

        ScrollView {
            VStack(alignment: .leading, spacing: 16) {

                // Harita
                if !locations.isEmpty {
                    DarkCard(title: "🗺️ Harita") {
                        MapView(locations: locations)
                            .frame(height: 200)
                            .cornerRadius(12)
                    }
                }

                // Şehirler / Lokasyonlar
                if !locations.isEmpty {
                    DarkCard(title: "🏙️ Bulunan Şehirler") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(locations, id: \.originalName) { loc in
                                HStack(spacing: 12) {
                                    Image(systemName: "mappin.circle.fill")
                                        .foregroundColor(.blue)
                                        .font(.title3)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(loc.originalName.capitalized)
                                            .foregroundColor(.white)
                                            .font(.subheadline)
                                            .fontWeight(.medium)
                                        if let name = loc.placeData?.name {
                                            Text(name)
                                                .foregroundColor(.white.opacity(0.5))
                                                .font(.caption)
                                                .lineLimit(1)
                                        }
                                    }
                                }
                            }
                        }
                    }
                } else if !nerLocations.isEmpty {
                    // Koordinat bulunamadı ama NER'den yerler çıktı
                    DarkCard(title: "📍 Tespit Edilen Yerler") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(nerLocations, id: \.self) { loc in
                                HStack(spacing: 10) {
                                    Image(systemName: "location.circle.fill")
                                        .foregroundColor(.purple)
                                    Text(loc.capitalized)
                                        .foregroundColor(.white)
                                        .font(.subheadline)
                                }
                            }
                        }
                    }
                }

                // OCR - Ekranda okunan yazılar (mekan adları)
                if !ocrPois.isEmpty || !ocrTexts.isEmpty {
                    let displayTexts = ocrPois.isEmpty ? ocrTexts : ocrPois
                    DarkCard(title: "📝 Videodaki Yazılar") {
                        FlowLayout(spacing: 8) {
                            ForEach(displayTexts.prefix(12), id: \.self) { text in
                                Text(text)
                                    .font(.caption)
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 5)
                                    .background(Color.blue.opacity(0.2))
                                    .cornerRadius(8)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(Color.blue.opacity(0.3), lineWidth: 1)
                                    )
                            }
                        }
                    }
                }

                // Ses Transkripsiyon
                if let t = transcript, !t.isEmpty {
                    DarkCard(title: "🎙️ Ses Transkripsiyonu") {
                        Text(t)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .lineSpacing(4)
                            .lineLimit(6)
                    }
                }

                // Seyahat İpuçları
                if !tips.isEmpty {
                    DarkCard(title: "💡 Seyahat İpuçları") {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(tips, id: \.location) { tip in
                                VStack(alignment: .leading, spacing: 6) {
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
                if let s = summary, !s.isEmpty {
                    DarkCard(title: "📖 Gezi Özeti") {
                        Text(s)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .lineSpacing(4)
                    }
                }

                // Veri yok mesajı
                if !hasAnyData {
                    DarkCard(title: "ℹ️ Bilgi") {
                        Text("Bu videodan lokasyon veya mekan bilgisi çıkarılamadı. Türkçe yazı veya yer adı içeren videolar deneyin.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                    }
                }

                // İşlem İstatistikleri
                if let processing = ai?.processingTime {
                    DarkCard(title: "⚡ İşlem Bilgisi") {
                        HStack(spacing: 20) {
                            StatItem(value: "\(Int(processing))s", label: "Süre")
                            StatItem(value: "\(video.duration ?? 0)s", label: "Video")
                            StatItem(value: "\(ai?.detections?.count ?? 0)", label: "Nesne")
                        }
                    }
                }
            }
            .padding()
        }
    }

    // MARK: - Polling

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
                    PersistenceService.shared.saveVideoResult(video)
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

// MARK: - FlowLayout (tag cloud)

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        let height = rows.map { $0.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0 }.reduce(0, +)
            + CGFloat(max(rows.count - 1, 0)) * spacing
        return CGSize(width: proposal.width ?? 0, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        var y = bounds.minY
        for row in rows {
            var x = bounds.minX
            let rowH = row.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0
            for view in row {
                let size = view.sizeThatFits(.unspecified)
                view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
            y += rowH + spacing
        }
    }

    private func computeRows(proposal: ProposedViewSize, subviews: Subviews) -> [[LayoutSubview]] {
        var rows: [[LayoutSubview]] = [[]]
        var x: CGFloat = 0
        let maxW = proposal.width ?? 300
        for view in subviews {
            let w = view.sizeThatFits(.unspecified).width
            if x + w > maxW && !rows[rows.count - 1].isEmpty {
                rows.append([])
                x = 0
            }
            rows[rows.count - 1].append(view)
            x += w + spacing
        }
        return rows
    }
}

// MARK: - MapView

struct MapView: UIViewRepresentable {
    let locations: [EnrichedLocation]

    func makeUIView(context: Context) -> MKMapView {
        MKMapView()
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.removeAnnotations(mapView.annotations)
        var coordinates: [CLLocationCoordinate2D] = []
        for location in locations {
            guard let lat = location.placeData?.location?.lat,
                  let lng = location.placeData?.location?.lng else { continue }
            let coord = CLLocationCoordinate2D(latitude: lat, longitude: lng)
            coordinates.append(coord)
            let pin = MKPointAnnotation()
            pin.coordinate = coord
            pin.title = location.originalName
            mapView.addAnnotation(pin)
        }
        if let first = coordinates.first {
            mapView.setRegion(MKCoordinateRegion(center: first, latitudinalMeters: 50000, longitudinalMeters: 50000), animated: false)
        }
    }
}

// MARK: - DarkCard

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
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.white.opacity(0.1), lineWidth: 1))
    }
}

// MARK: - StatItem

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

// MARK: - ShareSheet

import UIKit

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

#Preview {
    NavigationStack {
        ResultsView(videoId: 65)
    }
}
