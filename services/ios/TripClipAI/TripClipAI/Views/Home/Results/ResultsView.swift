import SwiftUI
import MapKit

// MARK: - Ana View

struct ResultsView: View {
    let videoId: Int
    var preloadedData: AIResults? = nil

    @State private var videoData: VideoResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var analysisStage = 0
    @State private var stageTimer: Timer?
    @State private var selectedLocation: EnrichedLocation?
    @State private var showShareSheet = false
    @State private var showInstagramShare = false
    @State private var pdfData: Data?
    @State private var shareImage: UIImage?

    // Analiz aşamaları
    let stages: [(icon: String, text: String)] = [
        ("video.fill",               "Video çerçeveleri ayrıştırılıyor..."),
        ("eye.fill",                 "Görüntüler AI ile analiz ediliyor..."),
        ("text.viewfinder",          "Metin ve tabelalar okunuyor..."),
        ("waveform",                 "Ses transkripsiyonu yapılıyor..."),
        ("brain.head.profile",       "Yerler ve mekanlar tanımlanıyor..."),
        ("map.fill",                 "Rota optimize ediliyor..."),
        ("sparkles",                 "Seyahat ipuçları oluşturuluyor..."),
    ]

    var body: some View {
        ZStack {
            // Arka plan gradyanı
            LinearGradient(
                colors: [Color(hex: "0A0E1A"), Color(hex: "0d1f35")],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if isLoading {
                analysisLoadingView
            } else if let video = videoData {
                resultsContent(video: video)
            } else if let error = errorMessage {
                errorView(message: error)
            }
        }
        .navigationTitle("Gezi Analizi")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            if let video = videoData {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button {
                            shareImage = TripShareCard.render(video: video)
                            showShareSheet = true
                        } label: {
                            Label("Instagram'da Paylaş", systemImage: "camera.filters")
                        }

                        Button {
                            shareImage = TripShareCard.render(video: video)
                            showShareSheet = true
                        } label: {
                            Label("Görsel Olarak Paylaş", systemImage: "photo")
                        }

                        Button {
                            pdfData = PDFExportService.generateTripPDF(video: video)
                            shareImage = nil
                            showShareSheet = true
                        } label: {
                            Label("PDF Olarak Paylaş", systemImage: "doc.fill")
                        }
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundColor(.white)
                    }
                }
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let img = shareImage {
                ShareSheet(items: [img])
            } else if let data = pdfData {
                ShareSheet(items: [data])
            }
        }
        .sheet(item: $selectedLocation) { loc in
            LocationDetailSheet(location: loc)
        }
        .task {
            if let preloaded = preloadedData {
                videoData = VideoResponse(id: videoId, filename: "", status: "completed",
                                          duration: nil, aiResults: preloaded)
                isLoading = false
            } else {
                startStageAnimation()
                await pollVideoStatus()
            }
        }
        .onDisappear { stageTimer?.invalidate() }
    }

    // MARK: - Analiz Yükleme Ekranı

    var analysisLoadingView: some View {
        VStack(spacing: 32) {
            // Dönen ikon
            ZStack {
                Circle()
                    .fill(Color.blue.opacity(0.1))
                    .frame(width: 110, height: 110)
                Circle()
                    .stroke(Color.blue.opacity(0.3), lineWidth: 2)
                    .frame(width: 110, height: 110)
                Image(systemName: stages[analysisStage].icon)
                    .font(.system(size: 36))
                    .foregroundColor(.blue)
                    .id(analysisStage) // animasyon için
                    .transition(.scale.combined(with: .opacity))
                    .animation(.spring(response: 0.4), value: analysisStage)
            }

            VStack(spacing: 8) {
                Text("AI Analiz Ediyor")
                    .font(.title2).fontWeight(.bold)
                    .foregroundColor(.white)
                Text(stages[analysisStage].text)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.6))
                    .multilineTextAlignment(.center)
                    .animation(.easeInOut, value: analysisStage)
                    .id(analysisStage)
            }

            // Aşama ilerleme barları
            HStack(spacing: 6) {
                ForEach(0..<stages.count, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 3)
                        .fill(i <= analysisStage ? Color.blue : Color.white.opacity(0.15))
                        .frame(height: 4)
                        .animation(.easeInOut(duration: 0.4), value: analysisStage)
                }
            }
            .padding(.horizontal, 40)

            Text("Bu işlem 1-5 dakika sürebilir")
                .font(.caption)
                .foregroundColor(.white.opacity(0.35))
        }
        .padding(40)
    }

    // MARK: - Hata

    func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 50))
                .foregroundColor(.orange)
            Text(message)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Button("Tekrar Dene") { Task { await pollVideoStatus() } }
                .foregroundColor(.blue)
        }
        .padding()
    }

    // MARK: - Sonuçlar

    @ViewBuilder
    func resultsContent(video: VideoResponse) -> some View {
        let ai = video.aiResults
        let locations   = ai?.nominatim?.deduplicatedLocations ?? []
        let nerLocs     = ai?.ner?.extractedLocations ?? []
        let ocrPois     = ai?.ocrPois ?? []
        let ocrTexts    = ai?.ocr?.extractedTexts ?? []
        let tips        = ai?.rag?.travelTips?.tips ?? []
        let summary     = ai?.rag?.travelTips?.summary
        let transcript  = ai?.audio?.transcription?.transcript
        let hasData     = !locations.isEmpty || !nerLocs.isEmpty || !ocrPois.isEmpty

        ScrollView {
            VStack(alignment: .leading, spacing: 14) {

                // ── Özet başlık banner ──
                summaryBanner(locations: locations, nerLocs: nerLocs, ocrCount: ocrPois.count)

                // ── Harita ──
                if !locations.isEmpty {
                    DarkCard(title: "🗺️ Rota Haritası") {
                        TripMapView(locations: locations)
                            .frame(height: 220)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
                            )
                    }
                }

                // ── Gezilen Mekanlar ──
                if !locations.isEmpty {
                    DarkCard(title: "📍 Bulunan Mekanlar (\(locations.count))") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(Array(locations.enumerated()), id: \.element.originalName) { idx, loc in
                                LocationRow(index: idx + 1, location: loc)
                                    .contentShape(Rectangle())
                                    .onTapGesture { selectedLocation = loc }
                            }
                        }
                    }
                } else if !nerLocs.isEmpty {
                    DarkCard(title: "📍 Tespit Edilen Yerler") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(nerLocs, id: \.self) { loc in
                                HStack(spacing: 10) {
                                    Image(systemName: "location.circle.fill")
                                        .foregroundColor(.purple)
                                    Text(loc.capitalized)
                                        .foregroundColor(.white).font(.subheadline)
                                }
                            }
                        }
                    }
                }

                // ── OCR — Videoda Okunan İşletmeler ──
                let displayTexts = ocrPois.isEmpty ? ocrTexts : ocrPois
                // Haritada zaten pinlenen yerleri OCR listesinden çıkar
                let geocodedNames = Set(locations.map { $0.originalName.lowercased() })
                let ungeocoded = displayTexts.filter { !geocodedNames.contains($0.lowercased()) }

                if !ungeocoded.isEmpty {
                    DarkCard(title: "🏪 Haritada Konumu Bulunamayan İşletmeler") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(ungeocoded.prefix(20), id: \.self) { text in
                                HStack(spacing: 10) {
                                    Image(systemName: poiIcon(text))
                                        .font(.caption)
                                        .foregroundColor(.orange)
                                        .frame(width: 18)
                                    Text(text)
                                        .font(.subheadline)
                                        .foregroundColor(.white.opacity(0.85))
                                    Spacer()
                                    // Apple Maps arama butonu
                                    Button {
                                        let query = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                                        if let url = URL(string: "maps://?q=\(query)") {
                                            UIApplication.shared.open(url)
                                        }
                                    } label: {
                                        Image(systemName: "map")
                                            .font(.caption)
                                            .foregroundColor(.blue)
                                            .padding(6)
                                            .background(Color.blue.opacity(0.12))
                                            .cornerRadius(6)
                                    }
                                }
                                .padding(.horizontal, 4)
                            }
                            Text("Tıklayarak Apple Maps'te arayabilirsin")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.3))
                                .padding(.top, 2)
                        }
                    }
                }

                // ── Ses Transkripsiyon ──
                if let t = transcript, !t.isEmpty {
                    DarkCard(title: "🎙️ Ses Transkripsiyonu") {
                        Text(t)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.75))
                            .lineSpacing(5)
                    }
                }

                // ── Seyahat İpuçları ──
                if !tips.isEmpty {
                    DarkCard(title: "💡 Seyahat İpuçları") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(tips, id: \.location) { tip in
                                HStack(alignment: .top, spacing: 12) {
                                    Image(systemName: "lightbulb.fill")
                                        .foregroundColor(.yellow).font(.caption)
                                        .padding(.top, 3)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(tip.location)
                                            .font(.caption).fontWeight(.semibold)
                                            .foregroundColor(.orange)
                                        Text(tip.tip)
                                            .font(.caption)
                                            .foregroundColor(.white.opacity(0.7))
                                    }
                                }
                                .padding(10)
                                .background(Color.white.opacity(0.04))
                                .cornerRadius(10)
                            }
                        }
                    }
                }

                // ── Gezi Özeti ──
                if let s = summary, !s.isEmpty {
                    DarkCard(title: "📖 Gezi Özeti") {
                        Text(s)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .lineSpacing(5)
                    }
                }

                // ── Veri yok ──
                if !hasData {
                    DarkCard(title: "ℹ️ Bilgi") {
                        Text("Bu videodan lokasyon veya mekan bilgisi çıkarılamadı.\nTürkçe ses ya da yer yazısı içeren videolar deneyin.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                            .lineSpacing(4)
                    }
                }

                // ── İstatistikler ──
                if let pt = ai?.processingTime {
                    DarkCard(title: "⚡ İşlem Bilgisi") {
                        HStack(spacing: 0) {
                            StatItem(value: "\(Int(pt))s",                    label: "Süre")
                            StatItem(value: "\(video.duration ?? 0)s",        label: "Video")
                            StatItem(value: "\(ai?.detections?.count ?? 0)",  label: "Nesne")
                            StatItem(value: "\(locations.count)",              label: "Mekan")
                        }
                    }
                }
            }
            .padding()
        }
    }

    // MARK: - Özet Banner

    @ViewBuilder
    func summaryBanner(locations: [EnrichedLocation], nerLocs: [String], ocrCount: Int) -> some View {
        let total = locations.count + (locations.isEmpty ? nerLocs.count : 0)
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(total > 0 ? "\(total) Mekan Bulundu" : "Analiz Tamamlandı")
                    .font(.title3).fontWeight(.bold).foregroundColor(.white)
                if let first = locations.first?.originalName.capitalized {
                    Text("İlk durak: \(first)")
                        .font(.caption).foregroundColor(.white.opacity(0.5))
                }
            }
            Spacer()
            if total > 0 {
                ZStack {
                    Circle().fill(Color.blue.opacity(0.2)).frame(width: 54, height: 54)
                    Text("\(total)")
                        .font(.title2).fontWeight(.black).foregroundColor(.blue)
                }
            }
        }
        .padding(16)
        .background(
            LinearGradient(colors: [Color.blue.opacity(0.15), Color.purple.opacity(0.1)],
                           startPoint: .leading, endPoint: .trailing)
        )
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.blue.opacity(0.2), lineWidth: 1))
    }

    // MARK: - POI İkon Yardımcısı

    func poiIcon(_ text: String) -> String {
        let t = text.lowercased()
        if t.contains("kafe") || t.contains("cafe") || t.contains("kahve") { return "cup.and.saucer.fill" }
        if t.contains("dürüm") || t.contains("kebap") || t.contains("lokant") || t.contains("restoran") { return "fork.knife" }
        if t.contains("fırın") || t.contains("pastane") || t.contains("börek") { return "birthday.cake.fill" }
        if t.contains("müze") || t.contains("han") || t.contains("saray") { return "building.columns.fill" }
        if t.contains("cami") || t.contains("türbe") || t.contains("kilise") { return "building.fill" }
        if t.contains("park") || t.contains("bahçe") { return "leaf.fill" }
        if t.contains("otel") || t.contains("pansiyon") { return "bed.double.fill" }
        return "storefront.fill"
    }

    // MARK: - Polling

    func startStageAnimation() {
        stageTimer = Timer.scheduledTimer(withTimeInterval: 12, repeats: true) { _ in
            withAnimation {
                analysisStage = (analysisStage + 1) % stages.count
            }
        }
    }

    func pollVideoStatus() async {
        isLoading = true
        for _ in 0..<120 {
            do {
                let video = try await APIService.shared.getVideoStatus(id: videoId)
                if video.status == "completed" {
                    PersistenceService.shared.saveVideoResult(video)
                    stageTimer?.invalidate()
                    await MainActor.run { videoData = video; isLoading = false }
                    return
                } else if video.status == "failed" {
                    stageTimer?.invalidate()
                    await MainActor.run { errorMessage = "Video işleme başarısız oldu."; isLoading = false }
                    return
                }
                try await Task.sleep(nanoseconds: 5_000_000_000)
            } catch {
                stageTimer?.invalidate()
                await MainActor.run { errorMessage = error.localizedDescription; isLoading = false }
                return
            }
        }
        stageTimer?.invalidate()
        await MainActor.run { errorMessage = "Zaman aşımı — lütfen tekrar deneyin."; isLoading = false }
    }
}

// MARK: - Konum Satırı

struct LocationRow: View {
    let index: Int
    let location: EnrichedLocation

    var body: some View {
        HStack(spacing: 12) {
            // Sıra numarası
            ZStack {
                Circle().fill(Color.blue.opacity(0.15)).frame(width: 32, height: 32)
                Text("\(index)").font(.caption).fontWeight(.bold).foregroundColor(.blue)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(location.originalName.capitalized)
                    .font(.subheadline).fontWeight(.semibold).foregroundColor(.white)
                if let name = location.placeData?.name {
                    Text(name)
                        .font(.caption).foregroundColor(.white.opacity(0.45)).lineLimit(1)
                }
            }

            Spacer()

            // Kategori rozeti
            if let cat = location.placeData?.category {
                Text(categoryEmoji(cat) + " " + cat)
                    .font(.caption2).fontWeight(.medium)
                    .foregroundColor(.orange.opacity(0.9))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
            }

            Image(systemName: "chevron.right")
                .font(.caption2).foregroundColor(.white.opacity(0.3))
        }
        .padding(10)
        .background(Color.white.opacity(0.04))
        .cornerRadius(12)
    }

    func categoryEmoji(_ cat: String) -> String {
        let map: [String: String] = [
            "Müze": "🏛️", "Kale": "🏰", "Tarihi Alan": "🏺",
            "Arkeolojik Alan": "⛏️", "Cami": "🕌", "Kilise": "⛪",
            "Anıt": "🗿", "Köprü": "🌉", "Kafe": "☕",
            "Restoran": "🍽️", "Bar": "🍺", "Yemek": "🥙",
            "Park": "🌳", "Doğa Alanı": "🌿", "Plaj": "🏖️",
            "Şelale": "💧", "Zirve": "⛰️", "Manzara Noktası": "👁️",
            "Galeri": "🖼️", "Tiyatro": "🎭", "Sinema": "🎬",
            "Konaklama": "🏨", "Turistik Alan": "📸",
            "İbadet Yeri": "🙏", "Şehir": "🏙️", "İlçe": "🏘️",
            "Köy": "🌾", "Mekan": "📍",
        ]
        return map[cat] ?? "📍"
    }
}

// MARK: - Konum Detay Sheet

struct LocationDetailSheet: View {
    let location: EnrichedLocation
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "0A0E1A").ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {

                        // Mini harita
                        if let lat = location.placeData?.location?.lat,
                           let lng = location.placeData?.location?.lng {
                            let coord = CLLocationCoordinate2D(latitude: lat, longitude: lng)
                            Map(coordinateRegion: .constant(
                                MKCoordinateRegion(center: coord,
                                                   latitudinalMeters: 2000,
                                                   longitudinalMeters: 2000)
                            ), annotationItems: [location]) { loc in
                                MapPin(coordinate: coord, tint: .blue)
                            }
                            .frame(height: 200)
                            .cornerRadius(16)
                        }

                        // Bilgiler
                        VStack(alignment: .leading, spacing: 12) {
                            if let cat = location.placeData?.category {
                                Text(categoryEmoji(cat) + " " + cat)
                                    .font(.caption).fontWeight(.semibold)
                                    .foregroundColor(.orange)
                                    .padding(.horizontal, 10).padding(.vertical, 4)
                                    .background(Color.orange.opacity(0.12))
                                    .cornerRadius(8)
                            }

                            Text(location.originalName.capitalized)
                                .font(.title2).fontWeight(.bold).foregroundColor(.white)

                            if let name = location.placeData?.name {
                                Text(name)
                                    .font(.subheadline).foregroundColor(.white.opacity(0.5))
                            }

                            if let imp = location.placeData?.importance {
                                HStack(spacing: 6) {
                                    Image(systemName: "star.fill").font(.caption).foregroundColor(.yellow)
                                    Text("Önem skoru: \(String(format: "%.2f", imp))")
                                        .font(.caption).foregroundColor(.white.opacity(0.5))
                                }
                            }
                        }

                        // Apple Maps butonu
                        if let lat = location.placeData?.location?.lat,
                           let lng = location.placeData?.location?.lng {
                            Button {
                                let url = URL(string: "maps://?daddr=\(lat),\(lng)&dirflg=d")!
                                UIApplication.shared.open(url)
                            } label: {
                                HStack {
                                    Image(systemName: "map.fill")
                                    Text("Apple Maps'te Aç")
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }

                            Button {
                                let url = URL(string: "https://www.google.com/maps/search/?api=1&query=\(lat),\(lng)")!
                                UIApplication.shared.open(url)
                            } label: {
                                HStack {
                                    Image(systemName: "globe")
                                    Text("Google Maps'te Aç")
                                        .fontWeight(.semibold)
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.white.opacity(0.08))
                                .foregroundColor(.white)
                                .cornerRadius(14)
                                .overlay(RoundedRectangle(cornerRadius: 14)
                                    .stroke(Color.white.opacity(0.1), lineWidth: 1))
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle(location.originalName.capitalized)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Kapat") { dismiss() }.foregroundColor(.white)
                }
            }
        }
    }

    func categoryEmoji(_ cat: String) -> String {
        let map: [String: String] = [
            "Müze":"🏛️","Kale":"🏰","Tarihi Alan":"🏺","Cami":"🕌",
            "Anıt":"🗿","Köprü":"🌉","Kafe":"☕","Restoran":"🍽️",
            "Park":"🌳","Plaj":"🏖️","Şelale":"💧","Zirve":"⛰️",
            "Turistik Alan":"📸","Konaklama":"🏨","Şehir":"🏙️","Mekan":"📍",
        ]
        return map[cat] ?? "📍"
    }
}

// MARK: - Harita

struct TripMapView: UIViewRepresentable {
    let locations: [EnrichedLocation]

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.mapType = .standard
        map.showsUserLocation = false
        return map
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.removeAnnotations(mapView.annotations)
        mapView.removeOverlays(mapView.overlays)

        var coords: [CLLocationCoordinate2D] = []
        for (i, loc) in locations.enumerated() {
            guard let lat = loc.placeData?.location?.lat,
                  let lng = loc.placeData?.location?.lng else { continue }
            let c = CLLocationCoordinate2D(latitude: lat, longitude: lng)
            coords.append(c)
            let pin = MKPointAnnotation()
            pin.coordinate = c
            pin.title = "\(i+1). \(loc.originalName.capitalized)"
            mapView.addAnnotation(pin)
        }

        // Rota çizgisi
        if coords.count > 1 {
            let polyline = MKPolyline(coordinates: coords, count: coords.count)
            mapView.addOverlay(polyline)
        }

        // Zoom
        if !coords.isEmpty {
            let rect = coords.reduce(MKMapRect.null) { rect, c in
                let point = MKMapPoint(c)
                let r = MKMapRect(x: point.x, y: point.y, width: 0, height: 0)
                return rect.union(r)
            }
            mapView.setVisibleMapRect(rect, edgePadding: UIEdgeInsets(top: 40, left: 40, bottom: 40, right: 40), animated: false)
        }
    }
}

// MARK: - FlowLayout

struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        let height = rows.map { $0.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0 }.reduce(0, +)
            + CGFloat(max(rows.count - 1, 0)) * spacing
        return CGSize(width: proposal.width ?? 0, height: height)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in computeRows(proposal: proposal, subviews: subviews) {
            var x = bounds.minX
            let h = row.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0
            for view in row {
                let s = view.sizeThatFits(.unspecified)
                view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
                x += s.width + spacing
            }
            y += h + spacing
        }
    }
    private func computeRows(proposal: ProposedViewSize, subviews: Subviews) -> [[LayoutSubview]] {
        var rows: [[LayoutSubview]] = [[]]
        var x: CGFloat = 0
        let maxW = proposal.width ?? 300
        for view in subviews {
            let w = view.sizeThatFits(.unspecified).width
            if x + w > maxW && !rows[rows.count-1].isEmpty { rows.append([]); x = 0 }
            rows[rows.count-1].append(view)
            x += w + spacing
        }
        return rows
    }
}

// MARK: - DarkCard

struct DarkCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.headline).foregroundColor(.white)
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.06))
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.white.opacity(0.08), lineWidth: 1))
    }
}

// MARK: - StatItem

struct StatItem: View {
    let value: String
    let label: String
    var body: some View {
        VStack(spacing: 4) {
            Text(value).font(.title3).fontWeight(.bold).foregroundColor(.white)
            Text(label).font(.caption).foregroundColor(.white.opacity(0.45))
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

// MARK: - EnrichedLocation: Identifiable

extension EnrichedLocation: Identifiable {
    public var id: String { originalName }
}

// MARK: - Preview

#Preview {
    NavigationStack { ResultsView(videoId: 1) }
}
